"""E14 store loader — file I/O and normalization for E14JsonStore."""
import json
import logging
import os
from typing import Dict, List, Optional

from services.e14_normalize import (
    CANONICAL_DEPARTMENTS,
    CANONICAL_MUNICIPALITIES,
    CANONICAL_PUESTOS,
    fuzzy_match,
    infer_from_filename,
    normalize_name,
    normalize_puesto,
)
from services.e14_constants import (
    MAX_VOTES_PER_MESA,
    compute_party_sum,
)
from services.e14_puesto_lookup import get_puesto_nombre
from services.ocr_agents.pipeline import run_validation_pipeline

logger = logging.getLogger(__name__)


def _should_skip_file(filename: str) -> bool:
    """Skip duplicates (1) and summary metadata files."""
    return "(1)" in filename or filename == "tesseract_summary.json"


def _parse_mesa_id(filename: str) -> str:
    """Extract mesa_id from filename pattern."""
    stem = (filename
            .replace(".pdf", "")
            .replace("_tesseract.json", "")
            .replace("_azure.json", ""))
    parts = stem.split("_")
    if len(parts) >= 10:
        return f"{parts[4]}-{parts[5]}-{parts[8]}-{parts[6]}-{parts[9]}"
    return stem[:20]


def _to_int_or_none(val) -> Optional[int]:
    if val is None:
        return None
    return int(val)


def _mtime_iso(filepath: str) -> str:
    """Return file modification time as UTC ISO string (fallback for processed_at)."""
    import datetime
    ts = os.path.getmtime(filepath)
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).isoformat()


def _load_single(filepath: str, idx: int) -> Optional[Dict]:
    """Load and normalize one Azure JSON file into a form dict."""
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load %s: %s", filepath, e)
        return None

    return _load_from_payload(data, idx=idx, filepath=filepath)


def _load_from_payload(
    data: Dict,
    idx: int,
    filepath: str = "",
    source_label: str = "api",
) -> Optional[Dict]:
    """Normalize one Azure payload dict into a form entry.

    Supports both file-backed and in-memory forms.
    """

    if not data.get("success", False):
        return None
    if data.get("_source") != "azure":
        return None

    filename = data.get("filename", os.path.basename(filepath) if filepath else "")
    if not filename:
        filename = f"{source_label}_{idx}.pdf"
    dept = fuzzy_match(
        normalize_name(data.get("departamento", "")), CANONICAL_DEPARTMENTS,
    )
    muni_candidates = CANONICAL_MUNICIPALITIES.get(dept, [])
    muni = normalize_name(data.get("municipio", ""))
    if muni_candidates:
        muni = fuzzy_match(muni, muni_candidates)
    dept, muni = infer_from_filename(filename, dept, muni)

    partidos = list(data.get("partidos", []))

    raw_total = data.get("total_votos", 0) or 0

    # Cap party votes only when Azure LLM has NOT already audited the entry.
    # Entries with audit_adjusted=True were validated by the LLM auditor — trust them.
    _cap = raw_total if raw_total > 0 else MAX_VOTES_PER_MESA // 4
    for p in partidos:
        if p.get("audit_adjusted"):
            continue
        v = p.get("votes") or 0
        if v > _cap:
            p["_correction"] = {"original_votes": v, "reason": f"votes ({v}) > cap ({_cap})"}
            p["votes"] = 0
            p["needs_review"] = True

    corrected_total = sum(p.get("votes", 0) for p in partidos)
    total_votos = raw_total if raw_total <= MAX_VOTES_PER_MESA else corrected_total

    sufragantes_e11 = _to_int_or_none(data.get("sufragantes_e11"))
    votos_en_urna = _to_int_or_none(data.get("votos_en_urna"))
    votos_no_marcados = _to_int_or_none(data.get("votos_no_marcados"))

    zona_cod = str(data.get("zona") or "")
    puesto_raw = str(data.get("puesto") or "")
    puesto_cod = (
        fuzzy_match(
            normalize_puesto(puesto_raw),
            CANONICAL_PUESTOS.get(muni, []),
            cutoff=0.75,
        )
        if muni in CANONICAL_PUESTOS
        else normalize_puesto(puesto_raw)
    )

    form: Dict = {
        "id": idx,
        "processed_at": (
            data.get("processed_at")
            or (_mtime_iso(filepath) if filepath and os.path.isfile(filepath) else "")
        ),
        "extraction_id": data.get("extraction_id", ""),
        "filename": filename,
        "filepath": filepath or "",
        "mesa_id": _parse_mesa_id(filename),
        "corporacion": (data.get("corporacion") or "").upper(),
        "departamento": dept,
        "municipio": muni,
        "zona_cod": zona_cod,
        "puesto_cod": puesto_cod,
        "mesa_num": data.get("mesa", ""),
        "ocr_processed": True,
        "ocr_confidence": data.get("confidence", 0),
        "total_votos": total_votos,
        "votos_blancos": data.get("votos_blancos"),
        "votos_nulos": data.get("votos_nulos"),
        "votos_no_marcados": votos_no_marcados if votos_no_marcados is not None else 0,
        "sufragantes_e11": sufragantes_e11 if sufragantes_e11 is not None else 0,
        "votos_en_urna": votos_en_urna if votos_en_urna is not None else 0,
        "partidos": partidos,
        "num_firmas": data.get("num_jurados_firmantes"),
        "lugar": (data.get("lugar") or "").strip(),
        "warnings": data.get("warnings", []),
        "_raw_sufragantes_e11": sufragantes_e11,
        "_raw_votos_en_urna": votos_en_urna,
        "_raw_votos_no_marcados": votos_no_marcados,
        "_raw_text": data.get("raw_text", ""),
    }

    form["puesto_nombre"] = get_puesto_nombre(muni, zona_cod, puesto_cod)
    form["validation"] = run_validation_pipeline(form)
    return form


def load_all_forms(data_dir: str) -> List[Dict]:
    """Read, normalize, dedup, and index all Azure JSON files in data_dir."""
    if not os.path.isdir(data_dir):
        logger.warning("E14 data dir not found: %s", data_dir)
        return []

    files = sorted(
        (f for f in os.listdir(data_dir)
         if f.endswith("_azure.json") and not _should_skip_file(f)),
        key=lambda f: os.path.getmtime(os.path.join(data_dir, f)),
    )

    forms = [
        form for fname in files
        if (form := _load_single(os.path.join(data_dir, fname), 0)) is not None
    ]

    # Dedup by physical mesa fields when available, fallback to mesa_id
    # mesa_num from Azure OCR correctly identifies the same physical mesa
    # even when processed from different filenames (test1 vs ej10 → same mesa)
    dedup: Dict[tuple, Dict] = {}
    for f in forms:
        mesa_num = f.get("mesa_num") or ""
        if mesa_num:
            key = (f["corporacion"], f["departamento"], f["municipio"],
                   f.get("zona_cod") or "", f.get("puesto_cod") or "", mesa_num)
        else:
            key = (f["corporacion"], f["departamento"], f["municipio"], f["mesa_id"])
        prev = dedup.get(key)
        if prev is None:
            dedup[key] = f
        else:
            # Prefer most recently processed; fall back to higher confidence on tie.
            def _ts(form: Dict) -> str:
                return form.get("processed_at") or ""

            newer = _ts(f) > _ts(prev)
            higher_conf = f["ocr_confidence"] > prev["ocr_confidence"]
            replace = newer or (not newer and higher_conf)

            if replace:
                logger.warning(
                    "E14 dup %s: replacing %s(%.2f, %s) with %s(%.2f, %s)",
                    key,
                    prev["filename"], prev["ocr_confidence"], _ts(prev),
                    f["filename"], f["ocr_confidence"], _ts(f),
                )
                dedup[key] = f
            else:
                logger.warning(
                    "E14 dup %s: dropping %s(%.2f, %s), keeping %s(%.2f, %s)",
                    key,
                    f["filename"], f["ocr_confidence"], _ts(f),
                    prev["filename"], prev["ocr_confidence"], _ts(prev),
                )
    forms = list(dedup.values())

    for i, f in enumerate(forms, start=1):
        f["id"] = i

    logger.info(
        "E14JsonStore: loaded %d forms from %s",
        len(forms), data_dir,
    )

    return forms
