"""Read-only queries for E14 dashboard from Azure SQL cache."""
from __future__ import annotations

import glob
import json
import logging
import os
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from config import Config
from services.e14_constants import OCR_HIGH_RISK_THRESHOLD, OCR_MEDIUM_RISK_THRESHOLD
from services.e14_store_loader import _load_from_payload

logger = logging.getLogger(__name__)
_CACHE_TTL_SECONDS = 20
_cache_lock = threading.Lock()
_cache_store: Dict[str, tuple[float, Any]] = {}

try:
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover
    pyodbc = None


def is_sql_mode() -> bool:
    return bool(getattr(Config, "E14_SQL_QUEUE_ENABLED", False))


def _connect():
    if not is_sql_mode():
        raise RuntimeError("SQL mode is disabled")
    if not Config.E14_SQL_CONNECTION_STRING:
        raise RuntimeError("E14_SQL_CONNECTION_STRING is empty")
    if pyodbc is None:
        raise RuntimeError("pyodbc is not installed")
    return pyodbc.connect(Config.E14_SQL_CONNECTION_STRING, timeout=30)


def _cache_get(key: str):
    now = time.time()
    with _cache_lock:
        item = _cache_store.get(key)
        if not item:
            return None
        ts, value = item
        if now - ts > _CACHE_TTL_SECONDS:
            _cache_store.pop(key, None)
            return None
        return value


def _cache_set(key: str, value: Any) -> Any:
    with _cache_lock:
        _cache_store[key] = (time.time(), value)
    return value


def _risk_where(risk: Optional[str]) -> Tuple[str, List[Any]]:
    if risk == "high":
        return " AND ocr_confidence < ? ", [float(OCR_HIGH_RISK_THRESHOLD)]
    if risk == "medium":
        return " AND ocr_confidence >= ? AND ocr_confidence < ? ", [
            float(OCR_HIGH_RISK_THRESHOLD), float(OCR_MEDIUM_RISK_THRESHOLD),
        ]
    if risk == "low":
        return " AND ocr_confidence >= ? ", [float(OCR_MEDIUM_RISK_THRESHOLD)]
    return "", []


def _base_where(
    corporacion: Optional[str] = None,
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
    puesto: Optional[str] = None,
    mesa: Optional[str] = None,
    risk: Optional[str] = None,
) -> Tuple[str, List[Any]]:
    clauses = ["1=1"]
    params: List[Any] = []
    if corporacion:
        clauses.append("corporacion = ?")
        params.append(corporacion.upper())
    if departamento:
        clauses.append("departamento = ?")
        params.append(departamento.upper())
    if municipio:
        clauses.append("municipio = ?")
        params.append(municipio.upper())
    if puesto:
        clauses.append("puesto_cod = ?")
        params.append(puesto)
    if mesa:
        clauses.append("mesa_num = ?")
        params.append(str(mesa))

    where = " AND ".join(clauses)
    rw, rparams = _risk_where(risk)
    if rw:
        where += rw
        params.extend(rparams)
    return where, params


def _normalize_cached_payload(payload: dict, idx: int) -> Optional[Dict[str, Any]]:
    """Convert cached normalized JSON into the same form shape used by in-memory store."""
    try:
        form = _load_from_payload(payload, idx=idx, filepath="", source_label="sql_cache")
        return form
    except Exception as exc:
        logger.warning("SQL cache payload normalization failed (idx=%s): %s", idx, exc)
        return None


def _summary_from_form(form: Dict[str, Any]) -> Dict[str, Any]:
    validation = form.get("validation", {})
    return {
        "id": form.get("id"),
        "mesa_id": form.get("mesa_id"),
        "filename": form.get("filename"),
        "corporacion": form.get("corporacion"),
        "departamento": form.get("departamento"),
        "municipio": form.get("municipio"),
        "zona_cod": form.get("zona_cod"),
        "puesto_cod": form.get("puesto_cod"),
        "puesto_nombre": form.get("puesto_nombre"),
        "lugar": form.get("lugar"),
        "mesa_num": form.get("mesa_num"),
        "ocr_confidence": form.get("ocr_confidence"),
        "total_votos": form.get("total_votos"),
        "votos_blancos": form.get("votos_blancos"),
        "votos_nulos": form.get("votos_nulos"),
        "ocr_processed": True,
        "is_valid": validation.get("is_valid", True),
        "auto_corrected": validation.get("auto_corrected", False),
        "needs_human_review": validation.get("needs_human_review", False),
        "review_priority": validation.get("review_priority", "NONE"),
    }


def get_forms(
    page: int = 1,
    per_page: int = 50,
    corporacion: Optional[str] = None,
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
    puesto: Optional[str] = None,
    mesa: Optional[str] = None,
    risk: Optional[str] = None,
) -> Dict[str, Any]:
    cache_key = f"forms|p={page}|pp={per_page}|c={corporacion}|d={departamento}|m={municipio}|pu={puesto}|me={mesa}|r={risk}"
    if cached := _cache_get(cache_key):
        return cached

    where, params = _base_where(corporacion, departamento, municipio, puesto, mesa, risk)
    page = max(1, int(page))
    per_page = max(1, min(500, int(per_page)))
    start_rn = (page - 1) * per_page + 1
    end_rn = start_rn + per_page - 1

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(1) FROM dbo.e14_results_cache WHERE {where}", params)
        total = int(cur.fetchone()[0] or 0)

        sql = f"""
        WITH filtered AS (
            SELECT
                document_id, result_json,
                ROW_NUMBER() OVER (ORDER BY synced_at DESC, document_id ASC) AS rn
            FROM dbo.e14_results_cache
            WHERE {where}
        )
        SELECT rn, document_id, result_json
        FROM filtered
        WHERE rn BETWEEN ? AND ?
        ORDER BY rn ASC
        """
        cur.execute(sql, [*params, start_rn, end_rn])
        rows = cur.fetchall()

    forms: List[Dict[str, Any]] = []
    for row in rows:
        rn = int(row[0])
        raw = row[2]
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        form = _normalize_cached_payload(payload, idx=rn)
        if not form:
            continue
        forms.append(_summary_from_form(form))

    return _cache_set(cache_key, {
        "forms": forms,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
    })


def get_forms_full(
    limit: int = 500,
    corporacion: Optional[str] = None,
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return normalized full forms (including partidos) for live dashboard payloads."""
    cache_key = f"forms_full|l={limit}|c={corporacion}|d={departamento}|m={municipio}"
    if cached := _cache_get(cache_key):
        return cached

    where, params = _base_where(
        corporacion=corporacion,
        departamento=departamento,
        municipio=municipio,
    )
    limit = max(1, min(1000, int(limit)))

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT TOP ({limit}) result_json
            FROM dbo.e14_results_cache
            WHERE {where}
            ORDER BY synced_at DESC, document_id ASC
            """,
            params,
        )
        rows = cur.fetchall()

    forms: List[Dict[str, Any]] = []
    idx = 1
    for row in rows:
        try:
            payload = json.loads(row[0])
        except Exception:
            continue
        form = _normalize_cached_payload(payload, idx=idx)
        if not form:
            continue
        forms.append(form)
        idx += 1
    return _cache_set(cache_key, forms)


def get_form_detail(form_id: int) -> Optional[Dict[str, Any]]:
    form_id = int(form_id)
    if form_id <= 0:
        return None
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            WITH ranked AS (
              SELECT
                result_json,
                ROW_NUMBER() OVER (ORDER BY synced_at DESC, document_id ASC) AS rn
              FROM dbo.e14_results_cache
            )
            SELECT result_json, rn
            FROM ranked
            WHERE rn = ?
            """,
            form_id,
        )
        row = cur.fetchone()
    if not row:
        return None
    try:
        payload = json.loads(row[0])
    except Exception:
        return None
    form = _normalize_cached_payload(payload, idx=form_id)
    if not form:
        return None

    out = _summary_from_form(form)
    out["partidos"] = form.get("partidos", [])
    out["validation"] = form.get("validation", {})
    out["sufragantes_e11"] = form.get("_raw_sufragantes_e11")
    out["votos_no_marcados"] = form.get("_raw_votos_no_marcados")
    out["votos_en_urna"] = form.get("_raw_votos_en_urna")
    out["num_firmas"] = form.get("num_firmas")
    out["warnings"] = form.get("warnings") or []
    out["raw_text"] = form.get("_raw_text", "")
    return out


def get_form_by_mesa_id(mesa_id: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT TOP 1 result_json
            FROM dbo.e14_results_cache
            WHERE mesa_id = ?
            ORDER BY synced_at DESC, document_id ASC
            """,
            mesa_id,
        )
        row = cur.fetchone()
    if not row:
        return None
    try:
        payload = json.loads(row[0])
    except Exception:
        return None
    form = _normalize_cached_payload(payload, idx=1)
    if not form:
        return None
    out = _summary_from_form(form)
    out["partidos"] = form.get("partidos", [])
    out["validation"] = form.get("validation", {})
    out["sufragantes_e11"] = form.get("_raw_sufragantes_e11")
    out["votos_no_marcados"] = form.get("_raw_votos_no_marcados")
    out["votos_en_urna"] = form.get("_raw_votos_en_urna")
    out["num_firmas"] = form.get("num_firmas")
    out["warnings"] = form.get("warnings") or []
    out["raw_text"] = form.get("_raw_text", "")
    return out


def get_form_by_identifier(identifier: str) -> Optional[Dict[str, Any]]:
    """Resolve a form by mesa_id/document_id (exact or prefix)."""
    ident = str(identifier or "").strip()
    if not ident:
        return None

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT TOP 1 result_json
            FROM dbo.e14_results_cache
            WHERE mesa_id = ?
               OR document_id = ?
               OR document_id LIKE ?
               OR JSON_VALUE(result_json, '$.extraction_id') = ?
               OR JSON_VALUE(result_json, '$.extraction_id') LIKE ?
               OR JSON_VALUE(result_json, '$.document_id') = ?
               OR JSON_VALUE(result_json, '$.document_id') LIKE ?
               OR JSON_VALUE(result_json, '$.metadata.document_id') = ?
               OR JSON_VALUE(result_json, '$.metadata.document_id') LIKE ?
               OR JSON_VALUE(result_json, '$.meta.document_id') = ?
               OR JSON_VALUE(result_json, '$.meta.document_id') LIKE ?
            ORDER BY synced_at DESC, document_id ASC
            """,
            ident,
            ident,
            f"{ident}%",
            ident,
            f"{ident}%",
            ident,
            f"{ident}%",
            ident,
            f"{ident}%",
            ident,
            f"{ident}%",
        )
        row = cur.fetchone()
        if not row:
            cur.execute(
                """
                SELECT TOP 1 result_json
                FROM dbo.e14_results_cache
                WHERE result_json LIKE ?
                ORDER BY synced_at DESC, document_id ASC
                """,
                f"%{ident}%",
            )
            row = cur.fetchone()
    if not row:
        return None
    try:
        payload = json.loads(row[0])
    except Exception:
        return None
    form = _normalize_cached_payload(payload, idx=1)
    if not form:
        return None
    out = _summary_from_form(form)
    out["partidos"] = form.get("partidos", [])
    out["validation"] = form.get("validation", {})
    out["sufragantes_e11"] = form.get("_raw_sufragantes_e11")
    out["votos_no_marcados"] = form.get("_raw_votos_no_marcados")
    out["votos_en_urna"] = form.get("_raw_votos_en_urna")
    out["num_firmas"] = form.get("num_firmas")
    out["warnings"] = form.get("warnings") or []
    out["raw_text"] = form.get("_raw_text", "")
    return out


def get_stats(
    departamento: Optional[str] = None,
    municipio: Optional[str] = None,
    puesto: Optional[str] = None,
    mesa: Optional[str] = None,
    risk: Optional[str] = None,
) -> Dict[str, Any]:
    cache_key = f"stats|d={departamento}|m={municipio}|p={puesto}|me={mesa}|r={risk}"
    if cached := _cache_get(cache_key):
        return cached

    where, params = _base_where(
        corporacion=None,
        departamento=departamento,
        municipio=municipio,
        puesto=puesto,
        mesa=mesa,
        risk=risk,
    )
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
              COUNT(1) AS total_forms,
              COALESCE(SUM(total_votos), 0) AS total_votos
            FROM dbo.e14_results_cache
            WHERE {where}
            """,
            params,
        )
        row = cur.fetchone()
        total_forms = int(row[0] or 0)
        total_votos = int(row[1] or 0)

        cur.execute(
            f"""
            SELECT corporacion, COUNT(1) AS c
            FROM dbo.e14_results_cache
            WHERE {where}
            GROUP BY corporacion
            """,
            params,
        )
        by_corp = {str(r[0] or ""): int(r[1] or 0) for r in cur.fetchall() if r[0]}

        cur.execute(
            f"""
            SELECT TOP 10 departamento, COUNT(1) AS c
            FROM dbo.e14_results_cache
            WHERE {where} AND departamento IS NOT NULL AND departamento <> ''
            GROUP BY departamento
            ORDER BY c DESC
            """,
            params,
        )
        top_dept = [{"departamento": str(r[0]), "count": int(r[1] or 0)} for r in cur.fetchall()]

        cur.execute(
            f"""
            SELECT
              AVG(CAST(ocr_confidence AS FLOAT)),
              MIN(CAST(ocr_confidence AS FLOAT)),
              MAX(CAST(ocr_confidence AS FLOAT))
            FROM dbo.e14_results_cache
            WHERE {where}
            """,
            params,
        )
        conf = cur.fetchone()

    total_pdfs_available = len(glob.glob(os.path.join(Config.E14_FLAT_DIR, "*.pdf")))
    result: Dict[str, Any] = {
        "total_forms": total_forms,
        "by_corporacion": by_corp,
        "ocr_completed": total_forms,
        "ocr_pending": 0,
        "ocr_progress": 100.0 if total_forms > 0 else 0,
        "top_departamentos": top_dept,
        "total_votos": total_votos,
        "votos_blancos": 0,
        "votos_nulos": 0,
        "total_pdfs_available": total_pdfs_available,
    }
    if total_forms > 0 and conf:
        avg_conf = float(conf[0] or 0.0)
        min_conf = float(conf[1] or 0.0)
        max_conf = float(conf[2] or 0.0)
        result["ocr_quality"] = {
            "avg_confidence": round(avg_conf * 100, 1),
            "min_confidence": round(min_conf * 100, 1),
            "max_confidence": round(max_conf * 100, 1),
            "arithmetic_errors": 0,
            "warnings_count": 0,
            "pct_of_total": 100.0,
        }
    return _cache_set(cache_key, result)


def get_departamentos(corporacion: Optional[str] = None) -> List[Dict[str, Any]]:
    cache_key = f"depts|c={corporacion}"
    if cached := _cache_get(cache_key):
        return cached

    where, params = _base_where(corporacion=corporacion)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT departamento, COUNT(1)
            FROM dbo.e14_results_cache
            WHERE {where} AND departamento IS NOT NULL AND departamento <> ''
            GROUP BY departamento
            ORDER BY COUNT(1) DESC
            """,
            params,
        )
        rows = cur.fetchall()
    return _cache_set(cache_key, [{"departamento": str(r[0]), "total_mesas": int(r[1]), "ocr_completed": int(r[1])} for r in rows])


def get_municipios(departamento: str) -> List[Dict[str, Any]]:
    cache_key = f"munis|d={departamento}"
    if cached := _cache_get(cache_key):
        return cached

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT municipio, COUNT(1), COALESCE(SUM(total_votos), 0)
            FROM dbo.e14_results_cache
            WHERE departamento = ? AND municipio IS NOT NULL AND municipio <> ''
            GROUP BY municipio
            ORDER BY COUNT(1) DESC
            """,
            departamento.upper(),
        )
        rows = cur.fetchall()
    return _cache_set(cache_key, [
        {
            "municipio": str(r[0]),
            "total_mesas": int(r[1]),
            "ocr_completed": int(r[1]),
            "total_votos": int(r[2] or 0),
        }
        for r in rows
    ])


def get_puestos(departamento: str, municipio: str) -> List[Dict[str, Any]]:
    cache_key = f"puestos|d={departamento}|m={municipio}"
    if cached := _cache_get(cache_key):
        return cached

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT puesto_cod, COUNT(1)
            FROM dbo.e14_results_cache
            WHERE departamento = ? AND municipio = ? AND puesto_cod IS NOT NULL AND puesto_cod <> ''
            GROUP BY puesto_cod
            ORDER BY COUNT(1) DESC
            """,
            departamento.upper(),
            municipio.upper(),
        )
        rows = cur.fetchall()
    return _cache_set(cache_key, [{"puesto_cod": str(r[0]), "total_mesas": int(r[1]), "ocr_completed": int(r[1])} for r in rows])


def get_mesas(departamento: str, municipio: str, puesto: str) -> List[Dict[str, Any]]:
    cache_key = f"mesas|d={departamento}|m={municipio}|p={puesto}"
    if cached := _cache_get(cache_key):
        return cached

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT mesa_num, COUNT(1)
            FROM dbo.e14_results_cache
            WHERE departamento = ? AND municipio = ? AND puesto_cod = ? AND mesa_num IS NOT NULL AND mesa_num <> ''
            GROUP BY mesa_num
            ORDER BY mesa_num ASC
            """,
            departamento.upper(),
            municipio.upper(),
            puesto,
        )
        rows = cur.fetchall()
    return _cache_set(cache_key, [{"mesa_num": str(r[0]), "count": int(r[1])} for r in rows])


def get_party_totals(
    limit: int = 30,
    departamento: Optional[str] = None,
    corporacion: Optional[str] = None,
) -> List[Dict[str, Any]]:
    cache_key = f"party_totals|l={limit}|d={departamento}|c={corporacion}"
    if cached := _cache_get(cache_key):
        return cached

    where, params = _base_where(corporacion=corporacion, departamento=departamento)
    limit = max(1, min(200, int(limit)))

    sql = f"""
    SELECT TOP ({limit})
      p.party_name,
      COALESCE(SUM(COALESCE(p.votes, 0)), 0) AS total_votes,
      COUNT(DISTINCT c.document_id) AS mesas_count,
      AVG(COALESCE(p.confidence, 0.0)) AS avg_confidence
    FROM dbo.e14_results_cache c
    CROSS APPLY OPENJSON(c.result_json, '$.partidos')
      WITH (
        party_name NVARCHAR(256) '$.party_name',
        votes INT '$.votes',
        confidence FLOAT '$.confidence'
      ) p
    WHERE {where}
      AND p.party_name IS NOT NULL
      AND p.party_name <> ''
    GROUP BY p.party_name
    ORDER BY total_votes DESC
    """
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()

    total_all = sum(int(r[1] or 0) for r in rows) or 1
    out: List[Dict[str, Any]] = []
    for r in rows:
        total_votes = int(r[1] or 0)
        out.append({
            "party_name": str(r[0] or ""),
            "total_votes": total_votes,
            "mesas_count": int(r[2] or 0),
            "avg_confidence": round(float(r[3] or 0.0), 2),
            "percentage": round((total_votes / total_all) * 100, 2),
            "reviewable_votes": 0,
            "reviewable_mesas": 0,
            "votes_high_risk": 0,
            "votes_medium_risk": 0,
            "votes_low_risk": total_votes,
        })
    return _cache_set(cache_key, out)


def get_votes_by_municipality(departamento: Optional[str] = None) -> List[Dict[str, Any]]:
    cache_key = f"votes_muni|d={departamento}"
    if cached := _cache_get(cache_key):
        return cached

    where, params = _base_where(departamento=departamento)
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT
              departamento, municipio,
              COALESCE(SUM(total_votos), 0) AS total_votos,
              COUNT(1) AS total_mesas
            FROM dbo.e14_results_cache
            WHERE {where}
            GROUP BY departamento, municipio
            ORDER BY total_votos DESC
            """,
            params,
        )
        muni_rows = cur.fetchall()

        cur.execute(
            f"""
            SELECT
              c.departamento, c.municipio,
              p.party_name,
              COALESCE(SUM(COALESCE(p.votes, 0)), 0) AS votes
            FROM dbo.e14_results_cache c
            CROSS APPLY OPENJSON(c.result_json, '$.partidos')
              WITH (
                party_name NVARCHAR(256) '$.party_name',
                votes INT '$.votes'
              ) p
            WHERE {where}
              AND p.party_name IS NOT NULL
              AND p.party_name <> ''
            GROUP BY c.departamento, c.municipio, p.party_name
            ORDER BY c.departamento, c.municipio, votes DESC
            """,
            params,
        )
        party_rows = cur.fetchall()

    party_map: Dict[str, List[tuple[str, int]]] = defaultdict(list)
    for r in party_rows:
        key = f"{str(r[0] or '')}|{str(r[1] or '')}"
        party_map[key].append((str(r[2] or ""), int(r[3] or 0)))

    result: List[Dict[str, Any]] = []
    for r in muni_rows:
        dept = str(r[0] or "")
        muni = str(r[1] or "")
        key = f"{dept}|{muni}"
        top = sorted(party_map.get(key, []), key=lambda x: x[1], reverse=True)[:5]
        result.append({
            "departamento": dept,
            "municipio": muni,
            "total_votos": int(r[2] or 0),
            "votos_blancos": 0,
            "votos_nulos": 0,
            "total_mesas": int(r[3] or 0),
            "top_parties": [{"party_name": n, "votes": v} for n, v in top],
        })
    return _cache_set(cache_key, result)


class _TransientStore:
    """Adapter so PMSN collector can run over SQL-loaded forms."""
    def __init__(self, forms: List[Dict[str, Any]]):
        self._forms = forms

    def _ensure_loaded(self) -> None:
        return None


def get_pmsn_alerts() -> Dict[str, Any]:
    cache_key = "pmsn_alerts"
    if cached := _cache_get(cache_key):
        return cached

    from services.e14_pmsn_collector import collect_pmsn_alerts
    forms = get_forms_full(limit=1000)
    store = _TransientStore(forms)
    return _cache_set(cache_key, collect_pmsn_alerts(store=store))


def get_department_metrics() -> Dict[str, Dict[str, Any]]:
    """Aggregate department metrics for choropleth panels."""
    cache_key = "dept_metrics"
    if cached := _cache_get(cache_key):
        return cached

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              departamento,
              COUNT(1) AS mesas_total,
              COALESCE(SUM(total_votos), 0) AS total_votos,
              COALESCE(SUM(TRY_CAST(JSON_VALUE(result_json, '$.votos_blancos') AS INT)), 0) AS votos_blancos,
              COALESCE(SUM(TRY_CAST(JSON_VALUE(result_json, '$.votos_nulos') AS INT)), 0) AS votos_nulos,
              AVG(CAST(COALESCE(ocr_confidence, 0) AS FLOAT)) AS avg_confidence,
              SUM(CASE WHEN ocr_confidence < ? THEN 1 ELSE 0 END) AS high_risk_count,
              SUM(CASE WHEN ocr_confidence >= ? AND ocr_confidence < ? THEN 1 ELSE 0 END) AS medium_risk_count,
              SUM(CASE WHEN ocr_confidence >= ? THEN 1 ELSE 0 END) AS low_risk_count
            FROM dbo.e14_results_cache
            WHERE departamento IS NOT NULL AND departamento <> ''
            GROUP BY departamento
            """,
            float(OCR_HIGH_RISK_THRESHOLD),
            float(OCR_HIGH_RISK_THRESHOLD),
            float(OCR_MEDIUM_RISK_THRESHOLD),
            float(OCR_MEDIUM_RISK_THRESHOLD),
        )
        rows = cur.fetchall()

    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        dept = str(r[0] or "").upper()
        if not dept:
            continue
        mesas_total = int(r[1] or 0)
        high = int(r[6] or 0)
        medium = int(r[7] or 0)
        out[dept] = {
            "mesas_total": mesas_total,
            "mesas_ocr": mesas_total,
            "mesas_anomalias": high + medium,
            "high_risk_count": high,
            "medium_risk_count": medium,
            "low_risk_count": int(r[8] or 0),
            "total_votos": int(r[2] or 0),
            "votos_blancos": int(r[3] or 0),
            "votos_nulos": int(r[4] or 0),
            "avg_confidence": round(float(r[5] or 0.0), 4),
        }
    return _cache_set(cache_key, out)


def get_department_incidents(departamento: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Build lightweight incident-like records from low-confidence forms."""
    cache_key = f"dept_incidents|d={departamento}|l={limit}"
    if cached := _cache_get(cache_key):
        return cached

    limit = max(1, min(200, int(limit)))
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT TOP ({limit})
              mesa_id, municipio, ocr_confidence, synced_at
            FROM dbo.e14_results_cache
            WHERE departamento = ?
            ORDER BY ocr_confidence ASC, synced_at DESC
            """,
            departamento.upper(),
        )
        rows = cur.fetchall()

    incidents: List[Dict[str, Any]] = []
    for idx, r in enumerate(rows, start=1):
        conf = float(r[2] or 0.0)
        if conf < OCR_HIGH_RISK_THRESHOLD:
            severity = "P1"
        elif conf < OCR_MEDIUM_RISK_THRESHOLD:
            severity = "P2"
        else:
            severity = "P3"
        incidents.append({
            "id": idx,
            "incident_type": "OCR_LOW_CONF",
            "severity": severity,
            "status": "OPEN",
            "mesa_id": str(r[0] or ""),
            "muni_name": str(r[1] or ""),
            "description": f"ocr_conf={conf:.0%}",
            "ocr_confidence": conf,
            "created_at": str(r[3]) if r[3] else "",
        })
    return _cache_set(cache_key, incidents)
