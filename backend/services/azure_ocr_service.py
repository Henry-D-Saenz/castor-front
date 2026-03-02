"""Azure OCR Service for E-14 electoral forms.

API: POST /upload → POST /analyze → GET /status → GET /results (party_tables embedded).
Field priority in normalize_to_form: *_adjusted > *_original > legacy (no suffix).
"""
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_BASE_URL: str = os.getenv(
    "AZURE_OCR_URL",
    "https://castor-ocr-hpcxdsbmeqgvdebd.centralus-01.azurewebsites.net",
)
_API_KEY: str = os.getenv("AZURE_OCR_API_KEY", "")

# DANE code prefix: "01 ANTIOQUIA" or "01 - ANTIOQUIA" → "ANTIOQUIA"
_DANE_PREFIX_RE = re.compile(r"^\d+\s*[-–]?\s*")


def _strip_dane(name: str) -> str:
    """Remove numeric DANE prefix."""
    return _DANE_PREFIX_RE.sub("", (name or "").strip()).strip()


def _infer_corporacion(filename: str, document_scope: str = "") -> str:
    """Determine corporacion from document_scope or filename fallback."""
    scope = document_scope.upper()
    if scope in ("SENADO", "CAMARA"):
        return scope
    return "SENADO" if "_SEN_" in filename.upper() else "CAMARA"


def _build_headers() -> dict:
    h = {"Content-Type": "application/json"}
    if _API_KEY:
        h["Authorization"] = f"Bearer {_API_KEY}"
    return h


def _dedup_partidos(partidos: list) -> list:
    """Client-side dedup: keep one entry per party_code (highest votes, then shorter name).
    Only called when server has NOT already deduplicated (Escenario E).
    """
    seen: dict = {}
    no_code: list = []
    for p in partidos:
        code = (p.get("party_code") or "").strip()
        if not code:
            no_code.append(p)
            continue
        if code not in seen:
            seen[code] = p
        else:
            existing = seen[code]
            new_votes = p.get("votes", 0)
            cur_votes = existing.get("votes", 0)
            if new_votes > cur_votes:
                seen[code] = p
            elif new_votes == cur_votes:
                if len(p.get("party_name", "")) < len(existing.get("party_name", "")):
                    seen[code] = p
    return list(seen.values()) + no_code


def _best_summary_votes(summary_votes: list) -> dict:
    """Pick the highest-confidence summary_votes entry."""
    if not summary_votes:
        return {}
    return max(summary_votes, key=lambda s: s.get("confidence") or 0)


def _server_deduped(ext_warnings: list) -> bool:
    """Return True if warnings signal server-side deduplication."""
    for w in ext_warnings:
        text = w if isinstance(w, str) else (w.get("message") or w.get("text") or "")
        if "Deduplicated" in text or "deduplicated" in text:
            return True
    return False


def _candidate_number(p: dict, vlt: str) -> "int | None":
    """Derive candidate slot: 0=lista, N=preferencial, None=unknown."""
    raw = p.get("candidate_number_adjusted") or p.get("candidate_number")
    if raw is not None:
        try:
            return int(raw)
        except (ValueError, TypeError):
            return 0
    return 0 if (not vlt or vlt == "SIN_VOTO_PREFERENTE") else None


def _validate_combined(p: dict) -> Optional[str]:
    """Sección 5 client validation: combined_mismatch and ocr_vs_final_mismatch."""
    combined   = p.get("combined_votes_adjusted")
    party_only = p.get("party_only_votes_adjusted")
    cand_sum   = p.get("candidate_votes_sum_adjusted")
    if None not in (combined, party_only, cand_sum):
        if int(combined) != int(party_only) + int(cand_sum):
            return f"combined_mismatch party={p.get('party_code')}: {combined}!={party_only}+{cand_sum}"
    ocr_total = p.get("total_votes_ocr_adjusted")
    adj_final = p.get("total_votes_adjusted_final")
    if ocr_total is not None and adj_final is not None and int(ocr_total) != int(adj_final):
        return f"ocr_vs_final_mismatch party={p.get('party_code')}: ocr={ocr_total} final={adj_final}"
    return None


def _party_votes(p: dict) -> int:
    """Resolve canonical vote count. Escenario C: SIN_VOTO_PREFERENTE without
    total_votes_ocr_adjusted → party_only_votes_adjusted. Else: adjusted_final chain.
    """
    vlt       = p.get("vote_list_type_adjusted") or p.get("vote_list_type") or ""
    ocr_total = p.get("total_votes_ocr_adjusted")
    if vlt == "SIN_VOTO_PREFERENTE" and ocr_total is None:
        return int(p.get("party_only_votes_adjusted") or p.get("party_only_votes") or 0)
    return int(
        p.get("total_votes_adjusted_final")
        or p.get("combined_votes_adjusted")
        or p.get("total_votes_adjusted")
        or p.get("combined_votes")
        or 0
    )


def normalize_to_form(
    results: dict,
    filename: str,
    document_id: str,
    metadata: Optional[dict] = None,
) -> dict:
    """Convert Azure /results into the schema e14_json_store expects.
    Escenario E: skip client dedup if server already deduped (warning contains "Deduplicated").
    summary_votes from /results or metadata fallback; None when Azure didn't extract them.
    """
    loc     = results.get("location") or {}
    e11     = results.get("e11_totals") or {}
    parties = results.get("party_tables") or []

    document_scope = (results.get("document_scope") or "UNKNOWN").upper()
    ext_val        = results.get("extraction_validation") or {}
    is_consistent  = bool(ext_val.get("is_consistent", False))
    ext_warnings   = ext_val.get("warnings") or []

    sv_list = results.get("summary_votes") or []
    if not sv_list and metadata:
        sv_list = metadata.get("summary_votes_blocks") or []
    sv     = _best_summary_votes(sv_list)
    has_sv = bool(sv)

    blancos = int(sv.get("votos_en_blanco") or 0) if has_sv else None
    nulos   = int(sv.get("votos_nulos") or 0) if has_sv else None
    no_marc = int(sv.get("votos_no_marcados") or 0) if has_sv else None

    partidos_raw: list = []
    for p in parties:
        name = (
            p.get("party_name_adjusted")
            or p.get("party_name_original")
            or p.get("party_name")
            or ""
        )
        if not name:
            continue

        code = (
            p.get("party_code_adjusted")
            or p.get("party_code_original")
            or p.get("party_code")
            or ""
        )
        vlt       = p.get("vote_list_type_adjusted") or p.get("vote_list_type") or ""
        conf      = float(p.get("total_votes_adjusted_confidence") or 0.5)
        audit_llm = bool(p.get("audit_adjusted_by_llm", False))

        # Scenario B: totals_match_adjusted is the authoritative flag
        totals_match = p.get("totals_match_adjusted")
        if totals_match is None:
            totals_match = p.get("totals_match", False)

        # Escenario C: SIN_VOTO_PREFERENTE con party_only_votes_confidence < 0.8 → needs_review
        _svp_conf = float(p.get("party_only_votes_confidence") or 0.5)
        low_conf_c = (
            vlt == "SIN_VOTO_PREFERENTE"
            and p.get("total_votes_ocr_adjusted") is None
            and _svp_conf < 0.8
        )
        needs_review = ((not totals_match) and (not audit_llm)) or low_conf_c

        _ocr_raw = p.get("total_votes_ocr_adjusted") or p.get("total_votes_ocr")
        partidos_raw.append({
            "party_name":          name,
            "party_name_original": p.get("party_name_original"),
            "party_code":          code,
            "votes":               _party_votes(p),
            "total_votes_ocr":     int(_ocr_raw) if _ocr_raw is not None else None,
            "confidence":          conf,
            "needs_review":        needs_review,
            "audit_adjusted":      audit_llm,
            "vote_list_type":      vlt,
            "candidate_number":    _candidate_number(p, vlt),
            "audit_notes":         p.get("audit_notes") or "",
            "audit_trigger":       p.get("audit_trigger") or "",
            "audit_agent":         p.get("audit_agent") or "",
        })

    # Escenario E: server already deduped → don't re-dedup
    partidos = (
        partidos_raw if _server_deduped(ext_warnings)
        else _dedup_partidos(partidos_raw)
    )

    # Validación cliente Sección 5: combined_mismatch y ocr_vs_final_mismatch
    client_warnings = [_validate_combined(p) for p in parties if _validate_combined(p)]
    if client_warnings:
        ext_warnings = list(ext_warnings) + client_warnings

    avg_conf    = (
        sum(p["confidence"] for p in partidos) / len(partidos) if partidos else 0.5
    )
    total_votos = int(e11.get("total_votos_urna") or 0)

    # Publication policy (Escenario A)
    all_tables_publishable = all(
        p["party_name"] and (not p["needs_review"] or p["audit_adjusted"])
        for p in partidos
    )
    auto_publish = (
        document_scope != "UNKNOWN" and is_consistent and all_tables_publishable
    )

    return {
        "_source":           "azure",
        "success":           True,
        "extraction_id":     document_id,
        "filename":          filename,
        "document_scope":    document_scope,
        "is_consistent":     is_consistent,
        "auto_publish":      auto_publish,
        "corporacion":       _infer_corporacion(filename, document_scope),
        "departamento":      _strip_dane(loc.get("departamento") or ""),
        "municipio":         _strip_dane(loc.get("municipio") or ""),
        "lugar":             (loc.get("lugar") or "").strip(),
        "zona":              str(loc.get("zona") or ""),
        "puesto":            str(loc.get("puesto") or ""),
        "mesa":              str(loc.get("mesa") or ""),
        "sufragantes_e11":   int(e11.get("total_sufragantes_e11") or 0) or None,
        "votos_en_urna":     total_votos or None,
        "total_votos":       total_votos,
        "votos_blancos":     blancos,
        "votos_nulos":       nulos,
        "votos_no_marcados": no_marc,
        "confidence":        round(avg_conf, 4),
        "partidos":          partidos,
        "warnings":          ext_warnings,
        "num_firmas":        None,
        "processed_at":      datetime.now(timezone.utc).isoformat(),
    }


# ── Azure API client ──────────────────────────────────────────────────────────

def upload_pdf(pdf_bytes: bytes, filename: str) -> str:
    """Upload PDF to Azure blob; returns document_id."""
    url = f"{_BASE_URL}/api/v1/documents/upload"
    headers = {"Authorization": f"Bearer {_API_KEY}"} if _API_KEY else {}
    resp = requests.post(
        url,
        files={"file": (filename, pdf_bytes, "application/pdf")},
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    doc_id = data.get("document_id") or data.get("id")
    if not doc_id:
        raise ValueError(f"Azure upload returned no document_id: {data}")
    logger.info("Uploaded %s → document_id=%s", filename, doc_id)
    return str(doc_id)


def trigger_analysis(document_id: str) -> None:
    """Fire async analysis for an uploaded document."""
    url = f"{_BASE_URL}/api/v1/documents/analyze"
    resp = requests.post(
        url, json={"document_id": document_id}, headers=_build_headers(), timeout=30,
    )
    resp.raise_for_status()
    logger.info("Analysis triggered for document_id=%s", document_id)


def poll_until_done(
    document_id: str,
    timeout: int = 2000,
    initial_wait: int = 10,
    poll_interval: int = 5,
) -> None:
    """Poll /status until processing ends. 404 during polling = job not yet registered.

    initial_wait: seconds to sleep before the first poll (Azure never completes in <45s
    for real actas, so the first ~20 polls at 2s were always wasted round-trips).
    poll_interval: seconds between subsequent polls.
    """
    url = f"{_BASE_URL}/api/v1/documents/{document_id}/status"
    if initial_wait > 0:
        logger.info("poll_until_done: waiting %ss before first poll (document_id=%s)", initial_wait, document_id)
        time.sleep(initial_wait)
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(url, headers=_build_headers(), timeout=30)
        if resp.status_code == 404:
            logger.debug("document_id=%s status=404 (not ready yet)", document_id)
            time.sleep(poll_interval)
            continue
        resp.raise_for_status()
        status = (resp.json().get("status") or "").lower()
        logger.debug("document_id=%s status=%s", document_id, status)
        if status == "completed":
            return
        if status == "failed":
            raise RuntimeError(f"Azure analysis failed for document_id={document_id}")
        time.sleep(poll_interval)
    raise TimeoutError(
        f"Azure analysis timed out after {timeout}s for document_id={document_id}"
    )


def get_metadata(document_id: str) -> dict:
    """Fetch /metadata (best-effort, does not raise on 404)."""
    url = f"{_BASE_URL}/api/v1/documents/{document_id}/metadata"
    try:
        resp = requests.get(url, headers=_build_headers(), timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as exc:
        logger.debug("get_metadata failed for %s: %s", document_id, exc)
    return {}


def get_results(document_id: str, retries: int = 5, retry_delay: float = 1.0) -> dict:
    """Fetch /results (includes embedded party_tables). Results expire shortly after processing."""
    url = f"{_BASE_URL}/api/v1/documents/{document_id}/results"
    for attempt in range(retries):
        resp = requests.get(url, headers=_build_headers(), timeout=30)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404 and attempt < retries - 1:
            logger.warning(
                "document_id=%s results not ready yet (attempt %d/%d), retrying...",
                document_id, attempt + 1, retries,
            )
            time.sleep(retry_delay)
            continue
        resp.raise_for_status()
    raise RuntimeError(
        f"Results not available for document_id={document_id} after {retries} attempts."
    )


# ── Public entry point ────────────────────────────────────────────────────────

def process_pdf_file(pdf_path: str, max_attempts: int = 3) -> dict:
    """Full pipeline: upload → analyze → poll → results → normalize.
    Retries with fresh upload on server-side failures (jobs can expire mid-processing).
    """
    path      = Path(pdf_path)
    filename  = path.name
    pdf_bytes = path.read_bytes()

    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            t_start = time.time()

            t0 = time.time()
            document_id = upload_pdf(pdf_bytes, filename)
            logger.info("upload_pdf done in %.1fs (document_id=%s)", time.time() - t0, document_id)

            trigger_analysis(document_id)

            t1 = time.time()
            poll_until_done(document_id)
            logger.info("poll_until_done done in %.1fs (document_id=%s)", time.time() - t1, document_id)

            t2 = time.time()
            results = get_results(document_id, retries=5, retry_delay=1.0)
            logger.info("get_results done in %.1fs", time.time() - t2)

            # Only fetch metadata if /results didn't include summary_votes
            metadata = get_metadata(document_id) if not results.get("summary_votes") else {}

            form = normalize_to_form(results, filename, document_id, metadata=metadata)
            logger.info("process_pdf_file total %.1fs for %s", time.time() - t_start, filename)
            return form
        except Exception as exc:
            last_error = exc
            logger.warning(
                "process_pdf_file attempt %d/%d failed for %s: %s",
                attempt, max_attempts, filename, exc,
            )
            if attempt < max_attempts:
                time.sleep(5)

    raise RuntimeError(
        f"Failed to process {filename} after {max_attempts} attempts: {last_error}"
    )
