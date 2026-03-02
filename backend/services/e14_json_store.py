"""E14 JSON Store - In-memory store for E14 OCR results (JSON, no SQLite)."""
import json
import logging
import os
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from services.e14_constants import (
    ANOMALY_NEEDS_REVIEW_DEFAULT,
    ARITH_WARN_TOL,
    OCR_HIGH_RISK_THRESHOLD,
    OCR_MEDIUM_RISK_THRESHOLD,
    compute_full_sum,
)
from services.e14_store_loader import load_all_forms

logger = logging.getLogger(__name__)


class E14JsonStore:
    """In-memory store for E14 OCR JSON files with TTL auto-reload."""

    TTL_SECONDS = 300  # 5 minutes

    def __init__(self, data_dir: Optional[str] = None):
        if data_dir:
            self._data_dir = data_dir
        else:
            from config import Config
            self._data_dir = Config.E14_AZURE_RESULTS_DIR

        self._forms: List[Dict] = []
        self._forms_by_id: Dict[int, Dict] = {}
        self._runtime_forms: List[Dict] = []
        self._loaded_at: float = 0
        self._file_count: int = 0
        self._lock = threading.Lock()

    def _ensure_loaded(self) -> None:
        """Reload if TTL expired or not yet loaded."""
        now = time.time()
        if self._forms and (now - self._loaded_at) < self.TTL_SECONDS:
            return
        with self._lock:
            if self._forms and (time.time() - self._loaded_at) < self.TTL_SECONDS:
                return
            self._reload()

    def _reload(self) -> None:
        """Delegate to loader and update internal state."""
        forms = load_all_forms(self._data_dir)
        self._forms = forms
        self._forms_by_id = {f["id"]: f for f in forms}
        self._file_count = len(forms)

        # Re-apply runtime-injected forms so TTL reload does not drop them.
        if self._runtime_forms:
            for rf in self._runtime_forms:
                self._upsert_form(dict(rf), source_label="runtime-reload", track_runtime=False)
        self._loaded_at = time.time()

    def inject_form(self, filepath: str) -> Optional[Dict]:
        """Load a single JSON file and inject it into the store without full reload.

        If the same physical mesa already exists (dedup key match), replaces it.
        Returns the injected form dict, or None if the file was filtered out.
        """
        from services.e14_store_loader import _load_single
        self._ensure_loaded()
        with self._lock:
            next_id = max(self._forms_by_id.keys(), default=0) + 1
            form = _load_single(filepath, next_id)
            if form is None:
                return None
            return self._upsert_form(form, source_label=filepath, track_runtime=False)

    def inject_form_data(self, form_data: Dict, source_label: str = "api") -> Optional[Dict]:
        """Inject a normalized Azure payload dict without writing to disk."""
        from services.e14_store_loader import _load_from_payload
        self._ensure_loaded()
        with self._lock:
            next_id = max(self._forms_by_id.keys(), default=0) + 1
            form = _load_from_payload(form_data, idx=next_id, filepath="", source_label=source_label)
            if form is None:
                return None
            return self._upsert_form(form, source_label=source_label, track_runtime=True)

    def has_extraction_id(self, extraction_id: str) -> bool:
        """Return True if a form with this extraction_id is already loaded."""
        self._ensure_loaded()
        key = str(extraction_id or "").strip()
        if not key:
            return False
        return any(str(f.get("extraction_id") or "").strip() == key for f in self._forms)

    # ── Query methods ─────────────────────────────────────────────────────────

    def get_stats(
        self,
        departamento: Optional[str] = None,
        municipio: Optional[str] = None,
        puesto: Optional[str] = None,
        mesa: Optional[str] = None,
        risk: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregate stats with optional filters."""
        self._ensure_loaded()
        forms = self._filter_forms(departamento=departamento, municipio=municipio)
        if puesto:
            forms = [f for f in forms if f["puesto_cod"] == puesto]
        if mesa:
            forms = [f for f in forms if f["mesa_num"] == mesa]
        if risk:
            forms = self._filter_by_risk(forms, risk)

        by_corp: Dict[str, int] = defaultdict(int)
        by_dept: Dict[str, int] = defaultdict(int)
        total_votos = votos_blancos = votos_nulos = 0
        for f in forms:
            by_corp[f["corporacion"]] += 1
            if f["departamento"]:
                by_dept[f["departamento"]] += 1
            total_votos += f["total_votos"]
            votos_blancos += f["votos_blancos"] or 0
            votos_nulos += f["votos_nulos"] or 0

        total = len(forms)
        top_dept = sorted(by_dept.items(), key=lambda x: x[1], reverse=True)[:10]

        from config import Config
        import glob as _glob
        _pdf_dir = Config.E14_FLAT_DIR
        total_pdfs_available = len(_glob.glob(os.path.join(_pdf_dir, "*.pdf")))

        result: Dict[str, Any] = {
            "total_forms": total, "by_corporacion": dict(by_corp),
            "ocr_completed": total, "ocr_pending": 0,
            "ocr_progress": 100.0 if total > 0 else 0,
            "top_departamentos": [{"departamento": d, "count": c} for d, c in top_dept],
            "total_votos": total_votos, "votos_blancos": votos_blancos,
            "votos_nulos": votos_nulos,
            "total_pdfs_available": total_pdfs_available,
        }
        if risk and forms:
            confs = [f["ocr_confidence"] for f in forms]

            def _has_arith(f: Dict) -> bool:
                fs = compute_full_sum(
                    f["partidos"], f["votos_blancos"] or 0,
                    f["votos_nulos"] or 0, f.get("votos_no_marcados") or 0,
                )
                return fs > 0 and f["total_votos"] > 0 and abs(fs - f["total_votos"]) > ARITH_WARN_TOL

            result["ocr_quality"] = {
                "avg_confidence": round(sum(confs) / len(confs) * 100, 1),
                "min_confidence": round(min(confs) * 100, 1),
                "max_confidence": round(max(confs) * 100, 1),
                "arithmetic_errors": sum(1 for f in forms if _has_arith(f)),
                "warnings_count": sum(1 for f in forms if f.get("warnings")),
                "pct_of_total": round(total / max(len(self._forms), 1) * 100, 1),
            }
        return result

    def get_forms(
        self,
        page: int = 1,
        per_page: int = 50,
        corporacion: Optional[str] = None,
        departamento: Optional[str] = None,
        municipio: Optional[str] = None,
        ocr_only: bool = False,
    ) -> Dict[str, Any]:
        """Paginated form list matching /api/e14-data/forms response."""
        self._ensure_loaded()
        filtered = self._filter_forms(corporacion, departamento, municipio)
        filtered.sort(key=lambda f: (f["departamento"], f["municipio"], f["mesa_id"]))

        total = len(filtered)
        offset = (page - 1) * per_page
        return {
            "forms": [self._form_summary(f) for f in filtered[offset: offset + per_page]],
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
        }

    def get_departamentos(self, corporacion: Optional[str] = None) -> List[Dict]:
        """Department list matching /api/e14-data/departamentos response."""
        self._ensure_loaded()
        groups: Dict[str, int] = defaultdict(int)
        for f in self._filter_forms(corporacion=corporacion):
            if f["departamento"]:
                groups[f["departamento"]] += 1
        result = [
            {"departamento": d, "total_mesas": c, "ocr_completed": c}
            for d, c in groups.items()
        ]
        return sorted(result, key=lambda x: x["total_mesas"], reverse=True)

    def get_municipios(self, departamento: str) -> List[Dict]:
        """Municipality list matching /api/e14-data/municipios response."""
        self._ensure_loaded()
        groups: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "votos": 0})
        for f in self._filter_forms(departamento=departamento):
            if f["municipio"]:
                g = groups[f["municipio"]]
                g["count"] += 1
                g["votos"] += f["total_votos"]
        result = [
            {"municipio": m, "total_mesas": g["count"],
             "ocr_completed": g["count"], "total_votos": g["votos"]}
            for m, g in groups.items()
        ]
        return sorted(result, key=lambda x: x["total_mesas"], reverse=True)

    def get_puestos(self, departamento: str, municipio: str) -> List[Dict]:
        """Polling station list matching /api/e14-data/puestos response."""
        self._ensure_loaded()
        filtered = [
            f for f in self._forms
            if f["departamento"] == departamento.upper()
            and f["municipio"] == municipio.upper()
        ]
        groups: Dict[str, int] = defaultdict(int)
        for f in filtered:
            groups[f["puesto_cod"]] += 1
        result = [
            {"puesto_cod": p, "total_mesas": c, "ocr_completed": c}
            for p, c in groups.items()
        ]
        return sorted(result, key=lambda x: x["total_mesas"], reverse=True)

    def get_mesas(self, departamento: str, municipio: str, puesto: str) -> List[Dict]:
        """Mesa list matching /api/e14-data/mesas response."""
        self._ensure_loaded()
        filtered = [
            f for f in self._forms
            if f["departamento"] == departamento.upper()
            and f["municipio"] == municipio.upper()
            and f["puesto_cod"] == puesto
        ]
        groups: Dict[str, int] = defaultdict(int)
        for f in filtered:
            groups[f["mesa_num"]] += 1
        return sorted(
            [{"mesa_num": m, "count": c} for m, c in groups.items()],
            key=lambda x: x["mesa_num"],
        )

    def get_form_detail(self, form_id: int) -> Optional[Dict]:
        """Single form with partidos, validation, lazy-loads raw_text."""
        self._ensure_loaded()
        form = self._forms_by_id.get(form_id)
        if not form:
            return None

        result = self._form_summary(form)
        result["partidos"] = [
            {
                "party_name":    p.get("party_name", ""),
                "party_code":    p.get("party_code", ""),
                "votes":         p.get("votes", 0),
                "confidence":    p.get("confidence", 0),
                "needs_review":  p.get("needs_review", False),
                "audit_adjusted": p.get("audit_adjusted", False),
                "audit_notes":   p.get("audit_notes", ""),
                "audit_trigger": p.get("audit_trigger", ""),
                **( {"_correction": p["_correction"]} if p.get("_correction") else {} ),
            }
            for p in form["partidos"]
        ]
        result["validation"] = form.get("validation", {})
        result["sufragantes_e11"] = form.get("_raw_sufragantes_e11")
        result["votos_no_marcados"] = form.get("_raw_votos_no_marcados")
        result["votos_en_urna"] = form.get("_raw_votos_en_urna")
        result["num_firmas"] = form.get("num_firmas") or form.get("num_jurados_firmantes")
        result["warnings"] = form.get("warnings") or []

        try:
            raw_text = form.get("_raw_text")
            if raw_text:
                result["raw_text"] = raw_text
            elif form.get("filepath"):
                with open(form["filepath"], "r", encoding="utf-8") as fh:
                    result["raw_text"] = json.load(fh).get("raw_text", "")
            else:
                result["raw_text"] = ""
        except (OSError, json.JSONDecodeError):
            result["raw_text"] = ""

        return result

    def get_form_by_mesa_id(self, mesa_id: str) -> Optional[Dict]:
        """Find form by mesa_id string and return full detail."""
        self._ensure_loaded()
        for form in self._forms:
            if form.get("mesa_id") == mesa_id:
                return self.get_form_detail(form["id"])
        return None

    # ── Analytics delegation ──────────────────────────────────────────────────

    def get_party_totals(self, **kwargs) -> List[Dict]:
        from services.e14_analytics import get_party_totals
        return get_party_totals(self, **kwargs)

    def get_summary_by_dept(self) -> List[Dict]:
        from services.e14_analytics import get_summary_by_dept
        return get_summary_by_dept(self)

    def get_anomalies(self, threshold: float = ANOMALY_NEEDS_REVIEW_DEFAULT) -> Dict[str, Any]:
        from services.e14_analytics import get_anomalies
        return get_anomalies(self, threshold)

    def get_confidence_distribution(self, bins: int = 10) -> List[Dict]:
        from services.e14_analytics import get_confidence_distribution
        return get_confidence_distribution(self, bins)

    def get_votes_by_municipality(self, **kwargs) -> List[Dict]:
        from services.e14_analytics import get_votes_by_municipality
        return get_votes_by_municipality(self, **kwargs)

    def get_zero_vote_alerts(self) -> Dict[str, Any]:
        from services.e14_analytics import get_zero_vote_alerts
        return get_zero_vote_alerts(self)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _filter_forms(
        self,
        corporacion: Optional[str] = None,
        departamento: Optional[str] = None,
        municipio: Optional[str] = None,
    ) -> List[Dict]:
        result = self._forms
        if corporacion:
            result = [f for f in result if f["corporacion"] == corporacion.upper()]
        if departamento:
            result = [f for f in result if f["departamento"] == departamento.upper()]
        if municipio:
            result = [f for f in result if f["municipio"] == municipio.upper()]
        return result

    @staticmethod
    def _filter_by_risk(forms: List[Dict], risk: str) -> List[Dict]:
        if risk == "high":
            return [f for f in forms if f["ocr_confidence"] < OCR_HIGH_RISK_THRESHOLD]
        if risk == "medium":
            return [
                f for f in forms
                if OCR_HIGH_RISK_THRESHOLD <= f["ocr_confidence"] < OCR_MEDIUM_RISK_THRESHOLD
            ]
        if risk == "low":
            return [f for f in forms if f["ocr_confidence"] >= OCR_MEDIUM_RISK_THRESHOLD]
        return forms

    _SUMMARY_KEYS = [
        "id", "mesa_id", "filename", "corporacion", "departamento",
        "municipio", "zona_cod", "puesto_cod", "puesto_nombre", "lugar", "mesa_num",
        "ocr_confidence", "total_votos", "votos_blancos", "votos_nulos",
    ]

    def _form_summary(self, form: Dict) -> Dict:
        out = {k: form[k] for k in self._SUMMARY_KEYS}
        out["ocr_processed"] = True
        v = form.get("validation", {})
        out["is_valid"] = v.get("is_valid", True)
        out["auto_corrected"] = v.get("auto_corrected", False)
        out["needs_human_review"] = v.get("needs_human_review", False)
        out["review_priority"] = v.get("review_priority", "NONE")
        return out

    @staticmethod
    def _dedup_key(form: Dict) -> tuple:
        """Physical mesa dedup key: corp/dept/muni/zona/puesto/mesa_num fallback mesa_id."""
        mesa_num = form.get("mesa_num") or ""
        if mesa_num:
            return (
                form["corporacion"],
                form["departamento"],
                form["municipio"],
                form.get("zona_cod") or "",
                form.get("puesto_cod") or "",
                mesa_num,
            )
        return (
            form["corporacion"],
            form["departamento"],
            form["municipio"],
            form["mesa_id"],
        )

    def _upsert_form(self, form: Dict, source_label: str, track_runtime: bool) -> Dict:
        """Replace/append one form based on physical mesa key."""
        key = self._dedup_key(form)
        for i, existing in enumerate(self._forms):
            if self._dedup_key(existing) == key:
                form["id"] = existing["id"]
                self._forms[i] = form
                self._forms_by_id[form["id"]] = form
                logger.info("inject_form: replaced existing form id=%d (%s)", form["id"], source_label)
                if track_runtime:
                    self._record_runtime_form(form)
                return form

        self._forms.append(form)
        self._forms_by_id[form["id"]] = form
        self._file_count = len(self._forms)
        logger.info("inject_form: added new form id=%d (%s)", form["id"], source_label)
        if track_runtime:
            self._record_runtime_form(form)
        return form

    def _record_runtime_form(self, form: Dict) -> None:
        """Persist runtime form copy so TTL reloads keep API-synced entries."""
        key = self._dedup_key(form)
        for i, existing in enumerate(self._runtime_forms):
            if self._dedup_key(existing) == key:
                self._runtime_forms[i] = dict(form)
                return
        self._runtime_forms.append(dict(form))


_store_instance: Optional[E14JsonStore] = None
_store_lock = threading.Lock()


def get_e14_json_store() -> E14JsonStore:
    """Get or create the singleton E14JsonStore instance."""
    global _store_instance
    if _store_instance is None:
        with _store_lock:
            if _store_instance is None:
                _store_instance = E14JsonStore()
    return _store_instance
