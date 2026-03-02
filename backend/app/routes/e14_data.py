"""
E-14 Data API Routes.

Provides access to E-14 OCR results loaded directly from JSON files.
No SQLite middleman - reads from data/e14/processed/azure_results/.
"""
import json
import logging
import os
import glob
import re
import shutil
import tempfile
import threading
import uuid
from typing import Optional

from flask import Blueprint, Response, jsonify, request, send_from_directory
import requests

logger = logging.getLogger(__name__)

from services.e14_constants import (
    ANOMALY_HIGH_RISK_THRESHOLD,
    ANOMALY_NEEDS_REVIEW_DEFAULT,
    ARITH_TOLERANCE,
    ARITH_WARN_TOL,
    OCR_HIGH_RISK_THRESHOLD,
    OCR_MEDIUM_RISK_THRESHOLD,
    REOCR_CONFIDENCE_THRESHOLD,
)
from services.e14_json_store import get_e14_json_store
from services.e14_validator import validate_form
from services.e14_corrections import validate_batch
from services.e14_pmsn_rules import collect_pmsn_alerts, run_pmsn_rules, get_municipios_pareto, sum_pmsn_votes
from services.e14_pmsn_collector import _RISK_DOWNGRADE, _RELEVANCE_FILTER_RULES
from services.e14_results_fetcher import fetch_normalized_form
from services import e14_sql_reader

e14_data_bp = Blueprint('e14_data', __name__, url_prefix='/api/e14-data')

# In-memory job store for async OCR uploads (job_id → state dict)
_upload_jobs: dict = {}
_bootstrap_started = False
_bootstrap_lock = threading.Lock()


def _safe_doc_id(document_id: str) -> str:
    """Sanitize document_id for filesystem-safe JSON filenames."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(document_id).strip())


def _extract_doc_id_from_filename(filename: str) -> str:
    """Extract UUID-like document_id from filename if present."""
    stem = os.path.splitext(os.path.basename(filename or ""))[0]
    if re.fullmatch(r"[0-9a-fA-F-]{36}", stem):
        return stem
    return ""


def _stream_pdf_from_blob(document_id: str, filename_hint: str = "") -> Optional[Response]:
    """Stream the original PDF from Blob by document_id without local persistence.

    Returns a Flask Response on success, None on failure or when storage is not configured.
    """
    if not document_id:
        return None

    from config import Config

    conn_str = (Config.AZURE_STORAGE_CONNECTION_STRING or "").strip()
    container = (Config.AZURE_STORAGE_CONTAINER_NAME or "").strip()
    if not conn_str or not container:
        return None

    try:
        from azure.storage.blob import BlobServiceClient
    except Exception as exc:
        logger.warning("azure-storage-blob unavailable; cannot stream PDF from Blob: %s", exc)
        return None

    try:
        service = BlobServiceClient.from_connection_string(conn_str)
        container_client = service.get_container_client(container)
        prefix = f"{document_id}/"
        candidates = [
            b for b in container_client.list_blobs(name_starts_with=prefix)
            if str(getattr(b, "name", "")).lower().endswith(".pdf")
        ]
        if not candidates:
            return None

        # Prefer latest uploaded PDF under the document prefix.
        blob_item = sorted(
            candidates,
            key=lambda b: getattr(b, "last_modified", None) or 0,
            reverse=True,
        )[0]
        blob_name = blob_item.name
        blob_client = container_client.get_blob_client(blob_name)
        blob_stream = blob_client.download_blob()

        def _generate():
            for chunk in blob_stream.chunks():
                if chunk:
                    yield chunk

        display_name = (
            os.path.basename(filename_hint)
            if str(filename_hint).lower().endswith(".pdf")
            else f"{document_id}.pdf"
        )
        logger.info("Streaming PDF from Blob: %s", blob_name)
        return Response(
            _generate(),
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{display_name}"',
                "Cache-Control": "no-store",
            },
            direct_passthrough=True,
        )
    except Exception as exc:
        logger.warning("Failed to stream PDF from Blob for %s: %s", document_id, exc)
        return None


def _extract_document_ids(raw_ids) -> list[str]:
    """Normalize raw ids input (list|string|single id) into unique ordered ids."""
    if isinstance(raw_ids, str):
        raw_ids = [x.strip() for x in re.split(r"[,\n\r\t ]+", raw_ids) if x.strip()]
    elif raw_ids is None:
        raw_ids = []
    elif not isinstance(raw_ids, list):
        raw_ids = [raw_ids]

    seen = set()
    out: list[str] = []
    for x in raw_ids:
        doc_id = str(x).strip()
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        out.append(doc_id)
    return out


def _sync_document_results(
    document_ids: list[str],
    clear_existing: bool = False,
    force_refresh: bool = False,
) -> tuple[dict, int]:
    """Fetch results for each document_id, normalize and inject in-memory store.

    Persistence strategy: keep only a local document_id registry (no per-doc JSON files).
    """
    from config import Config
    from services.e14_document_registry import get_registry

    if not document_ids:
        return {'success': False, 'error': 'No document_ids provided'}, 400

    store = get_e14_json_store()
    registry = get_registry()

    deleted_files = 0  # retained for backward compatibility in response schema
    if clear_existing:
        registry.clear()
        with store._lock:
            store._forms = []
            store._forms_by_id = {}
            store._runtime_forms = []
            store._file_count = 0
            store._loaded_at = 0

    synced = []
    skipped = []
    errors = []

    for document_id in document_ids:
        try:
            if not force_refresh and store.has_extraction_id(document_id):
                skipped.append({
                    'document_id': document_id,
                    'reason': 'already_loaded_in_memory',
                })
                continue

            form = fetch_normalized_form(document_id)
            filename = os.path.basename(str(form.get("filename") or f"{document_id}.pdf"))
            injected = store.inject_form_data(form, source_label=f"document_id:{document_id}")
            if injected is None:
                raise RuntimeError("Form could not be injected into store")

            registry.add_ids([document_id])
            synced.append({
                'document_id': document_id,
                'form_id': injected.get('id'),
                'filename': filename,
                'departamento': injected.get('departamento'),
                'municipio': injected.get('municipio'),
                'mesa_id': injected.get('mesa_id'),
                'confidence': injected.get('ocr_confidence'),
            })
        except Exception as exc:
            logger.error("sync_document_results failed for %s: %s", document_id, exc)
            errors.append({'document_id': document_id, 'error': str(exc)})

    payload = {
        'success': len(errors) == 0,
        'requested': len(document_ids),
        'synced_count': len(synced),
        'skipped_count': len(skipped),
        'error_count': len(errors),
        'clear_existing': clear_existing,
        'deleted_files': deleted_files,
        'synced': synced,
        'skipped': skipped,
        'errors': errors,
    }
    return payload, (200 if len(errors) == 0 else 207)


def _chunks(values: list[str], size: int) -> list[list[str]]:
    """Split values into fixed-size chunks preserving order."""
    if size <= 0:
        size = 50
    return [values[i:i + size] for i in range(0, len(values), size)]


def _bootstrap_registry_worker() -> None:
    """Replay persisted document IDs at startup to rebuild in-memory store."""
    from config import Config
    from services.e14_document_registry import get_registry

    try:
        document_ids = get_registry().list_ids()
        if not document_ids:
            logger.info("E14 bootstrap: no document IDs found in registry")
            return

        batch_size = int(getattr(Config, "E14_BOOTSTRAP_BATCH_SIZE", 50) or 50)
        batches = _chunks(document_ids, batch_size)
        total_synced = 0
        total_skipped = 0
        total_errors = 0

        logger.info(
            "E14 bootstrap: replaying %d document IDs in %d batches (size=%d)",
            len(document_ids), len(batches), batch_size
        )

        for idx, batch in enumerate(batches, start=1):
            payload, status = _sync_document_results(
                batch,
                clear_existing=False,
                force_refresh=False,
            )
            total_synced += int(payload.get("synced_count", 0) or 0)
            total_skipped += int(payload.get("skipped_count", 0) or 0)
            total_errors += int(payload.get("error_count", 0) or 0)
            logger.info(
                "E14 bootstrap batch %d/%d: status=%d synced=%d skipped=%d errors=%d",
                idx, len(batches), status,
                int(payload.get("synced_count", 0) or 0),
                int(payload.get("skipped_count", 0) or 0),
                int(payload.get("error_count", 0) or 0),
            )

        logger.info(
            "E14 bootstrap finished: requested=%d synced=%d skipped=%d errors=%d",
            len(document_ids), total_synced, total_skipped, total_errors
        )
    except Exception as exc:
        logger.error("E14 bootstrap failed: %s", exc, exc_info=True)


def start_registry_bootstrap_async() -> bool:
    """Start one-time startup bootstrap thread. Returns True if thread started."""
    from config import Config

    if bool(getattr(Config, "E14_SQL_QUEUE_ENABLED", False)):
        logger.info("E14 registry bootstrap skipped: SQL queue mode enabled")
        return False

    if not bool(getattr(Config, "E14_BOOTSTRAP_FROM_REGISTRY", True)):
        logger.info("E14 bootstrap disabled by config")
        return False

    global _bootstrap_started
    with _bootstrap_lock:
        if _bootstrap_started:
            return False
        _bootstrap_started = True

    t = threading.Thread(
        target=_bootstrap_registry_worker,
        name="e14-registry-bootstrap",
        daemon=True,
    )
    t.start()
    return True


def _find_pmsn_party(partidos: list) -> tuple:
    """Return (party_name, party_votes) for the PMSN candidate party, or (None, 0)."""
    import unicodedata
    def _norm(s: str) -> str:
        return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii').upper()

    for p in partidos:
        name_norm = _norm(p.get('party_name') or '')
        if ('SALVACION' in name_norm or 'PMSN' in name_norm) and 'NUEVO LIBERALISMO' not in name_norm:
            return p.get('party_name', ''), int(p.get('votes') or 0)
    return None, 0


def _enrich_pmsn_alerts(form: dict) -> list:
    """Run PMSN rules and enrich each alert with pmsn_votes, pmsn_relevant,
    pmsn_party_name, pmsn_party_votes, and relevance-based risk downgrade."""
    raw_alerts = run_pmsn_rules(form, municipios_pareto=get_municipios_pareto())
    pmsn_v = sum_pmsn_votes(form.get('partidos', []))
    pmsn_rel = pmsn_v > 0
    party_name, party_votes = _find_pmsn_party(form.get('partidos', []))
    enriched = []
    for a in raw_alerts:
        rt = a['risk_type']
        if not pmsn_rel and a['rule_id'] in _RELEVANCE_FILTER_RULES:
            rt = _RISK_DOWNGRADE[rt]
        enriched.append({
            **a,
            'risk_type': rt,
            'pmsn_votes': pmsn_v,
            'pmsn_relevant': pmsn_rel,
            'pmsn_party_name': party_name,
            'pmsn_party_votes': party_votes,
        })
    return enriched


@e14_data_bp.route('/config', methods=['GET'])
def get_config():
    """Expose validation thresholds so the frontend stays in sync."""
    return jsonify({
        "ocr_high_risk": OCR_HIGH_RISK_THRESHOLD,
        "ocr_medium_risk": OCR_MEDIUM_RISK_THRESHOLD,
        "anomaly_high_risk": ANOMALY_HIGH_RISK_THRESHOLD,
        "anomaly_needs_review": ANOMALY_NEEDS_REVIEW_DEFAULT,
        "arith_tolerance": ARITH_TOLERANCE,
        "arith_warn_tol": ARITH_WARN_TOL,
        "reocr_threshold": REOCR_CONFIDENCE_THRESHOLD,
    })


@e14_data_bp.route('/reload', methods=['POST'])
def reload_store():
    """Invalidate the in-memory store TTL so the next request reloads from disk."""
    store = get_e14_json_store()
    store._loaded_at = 0
    store._ensure_loaded()
    return jsonify({'reloaded': True, 'total_forms': store._file_count})


@e14_data_bp.route('/documents/sync', methods=['POST'])
def sync_document_results():
    """
    Sync Azure OCR results by document IDs.

    Body:
      {
        "document_ids": ["id-1", "id-2", ...],
        "clear_existing": false
      }
    """
    body = request.get_json(silent=True) or {}
    raw_ids = body.get('document_ids') or body.get('ids') or body.get('document_id')
    clear_existing = bool(body.get('clear_existing', False))
    force_refresh = bool(body.get('force_refresh', False))
    document_ids = _extract_document_ids(raw_ids)
    payload, status = _sync_document_results(
        document_ids,
        clear_existing=clear_existing,
        force_refresh=force_refresh,
    )
    return jsonify(payload), status


@e14_data_bp.route('/webhook/completed', methods=['POST'])
def webhook_completed():
    """Webhook endpoint for upstream apps to push completed OCR document IDs."""
    from config import Config

    expected_token = (Config.OCR_WEBHOOK_TOKEN or '').strip()
    if not expected_token:
        return jsonify({'success': False, 'error': 'Webhook token is not configured'}), 503

    received_token = (request.headers.get('X-Webhook-Token') or '').strip()
    if received_token != expected_token:
        return jsonify({'success': False, 'error': 'Unauthorized webhook'}), 401

    body = request.get_json(silent=True) or {}
    raw_ids = body.get('document_ids') or body.get('ids') or body.get('document_id')
    clear_existing = bool(body.get('clear_existing', False))
    force_refresh = bool(body.get('force_refresh', False))
    document_ids = _extract_document_ids(raw_ids)
    if not document_ids:
        return jsonify({'success': False, 'error': 'No document_ids provided'}), 400

    if bool(getattr(Config, "E14_SQL_QUEUE_ENABLED", False)):
        try:
            from services.e14_document_registry import get_registry
            from services.e14_sql_queue import enqueue_document

            queued = 0
            for document_id in document_ids:
                enqueue_document(document_id, source="webhook")
                queued += 1
            # Keep local registry for audit/backward compatibility.
            get_registry().add_ids(document_ids)

            return jsonify({
                'success': True,
                'source': 'webhook',
                'queued_count': queued,
                'requested': len(document_ids),
                'clear_existing': clear_existing,
                'force_refresh': force_refresh,
                'mode': 'sql_queue',
            }), 202
        except Exception as exc:
            logger.error("webhook enqueue failed: %s", exc, exc_info=True)
            return jsonify({'success': False, 'error': f'Queue enqueue failed: {exc}'}), 500

    payload, status = _sync_document_results(
        document_ids,
        clear_existing=clear_existing,
        force_refresh=force_refresh,
    )
    payload['source'] = 'webhook'
    return jsonify(payload), status


@e14_data_bp.route('/stats', methods=['GET'])
def get_stats():
    """Get statistics of loaded E-14 forms, with optional filters."""
    if e14_sql_reader.is_sql_mode():
        return jsonify(e14_sql_reader.get_stats(
            departamento=request.args.get('departamento'),
            municipio=request.args.get('municipio'),
            puesto=request.args.get('puesto'),
            mesa=request.args.get('mesa'),
            risk=request.args.get('risk'),
        ))

    store = get_e14_json_store()
    return jsonify(store.get_stats(
        departamento=request.args.get('departamento'),
        municipio=request.args.get('municipio'),
        puesto=request.args.get('puesto'),
        mesa=request.args.get('mesa'),
        risk=request.args.get('risk'),
    ))


@e14_data_bp.route('/forms', methods=['GET'])
def get_forms():
    """Get paginated list of E-14 forms with optional filters."""
    if e14_sql_reader.is_sql_mode():
        result = e14_sql_reader.get_forms(
            page=request.args.get('page', 1, type=int),
            per_page=request.args.get('per_page', 50, type=int),
            corporacion=request.args.get('corporacion'),
            departamento=request.args.get('departamento'),
            municipio=request.args.get('municipio'),
            puesto=request.args.get('puesto'),
            mesa=request.args.get('mesa'),
            risk=request.args.get('risk'),
        )
        return jsonify(result)

    store = get_e14_json_store()
    result = store.get_forms(
        page=request.args.get('page', 1, type=int),
        per_page=request.args.get('per_page', 50, type=int),
        corporacion=request.args.get('corporacion'),
        departamento=request.args.get('departamento'),
        municipio=request.args.get('municipio'),
        ocr_only=request.args.get('ocr_only', 'false').lower() == 'true',
    )
    return jsonify(result)


@e14_data_bp.route('/departamentos', methods=['GET'])
def get_departamentos():
    """Get list of departments with form counts."""
    if e14_sql_reader.is_sql_mode():
        return jsonify(e14_sql_reader.get_departamentos(
            corporacion=request.args.get('corporacion'),
        ))

    store = get_e14_json_store()
    return jsonify(store.get_departamentos(
        corporacion=request.args.get('corporacion'),
    ))


@e14_data_bp.route('/municipios/<departamento>', methods=['GET'])
def get_municipios(departamento: str):
    """Get list of municipalities for a department."""
    if e14_sql_reader.is_sql_mode():
        return jsonify(e14_sql_reader.get_municipios(departamento))

    store = get_e14_json_store()
    return jsonify(store.get_municipios(departamento))


@e14_data_bp.route('/puestos/<departamento>/<municipio>', methods=['GET'])
def get_puestos(departamento: str, municipio: str):
    """Get polling stations for a department/municipality."""
    if e14_sql_reader.is_sql_mode():
        return jsonify(e14_sql_reader.get_puestos(departamento, municipio))

    store = get_e14_json_store()
    return jsonify(store.get_puestos(departamento, municipio))


@e14_data_bp.route('/mesas/<departamento>/<municipio>/<puesto>', methods=['GET'])
def get_mesas(departamento: str, municipio: str, puesto: str):
    """Get mesa numbers for a given puesto."""
    if e14_sql_reader.is_sql_mode():
        return jsonify(e14_sql_reader.get_mesas(departamento, municipio, puesto))

    store = get_e14_json_store()
    return jsonify(store.get_mesas(departamento, municipio, puesto))


@e14_data_bp.route('/party-totals', methods=['GET'])
def get_party_totals():
    """Get vote totals aggregated by party."""
    if e14_sql_reader.is_sql_mode():
        return jsonify(e14_sql_reader.get_party_totals(
            limit=request.args.get('limit', 30, type=int),
            departamento=request.args.get('departamento'),
            corporacion=request.args.get('corporacion'),
        ))

    store = get_e14_json_store()
    return jsonify(store.get_party_totals(
        limit=request.args.get('limit', 30, type=int),
        departamento=request.args.get('departamento'),
        corporacion=request.args.get('corporacion'),
    ))


@e14_data_bp.route('/form/<int:form_id>', methods=['GET'])
def get_form_detail(form_id: int):
    """Get detailed form data including party votes and PMSN alerts."""
    if e14_sql_reader.is_sql_mode():
        form = e14_sql_reader.get_form_detail(form_id)
        if not form:
            return jsonify({'error': 'Form not found'}), 404
        form['pmsn_alerts'] = _enrich_pmsn_alerts(form)
        return jsonify(form)

    store = get_e14_json_store()
    form = store.get_form_detail(form_id)
    if not form:
        return jsonify({'error': 'Form not found'}), 404
    form['pmsn_alerts'] = _enrich_pmsn_alerts(form)
    return jsonify(form)


@e14_data_bp.route('/form-by-mesa/<path:mesa_id>', methods=['GET'])
def get_form_by_mesa(mesa_id: str):
    """Get form detail by mesa_id string (e.g. '01-001-02-003-026')."""
    if e14_sql_reader.is_sql_mode():
        form = e14_sql_reader.get_form_by_mesa_id(mesa_id)
        if not form:
            return jsonify({'error': 'Form not found for mesa_id'}), 404
        form['pmsn_alerts'] = _enrich_pmsn_alerts(form)
        return jsonify(form)

    store = get_e14_json_store()
    form = store.get_form_by_mesa_id(mesa_id)
    if not form:
        return jsonify({'error': 'Form not found for mesa_id'}), 404
    form['pmsn_alerts'] = _enrich_pmsn_alerts(form)
    return jsonify(form)


@e14_data_bp.route('/anomalies', methods=['GET'])
def get_anomalies():
    """Get forms classified by OCR quality and arithmetic errors."""
    store = get_e14_json_store()
    threshold = request.args.get('threshold', ANOMALY_NEEDS_REVIEW_DEFAULT, type=float)
    return jsonify(store.get_anomalies(threshold=threshold))


@e14_data_bp.route('/zero-vote-alerts', methods=['GET'])
def get_zero_vote_alerts():
    """Parties with 0 votes in forms where they appear, ranked by suspicion."""
    store = get_e14_json_store()
    return jsonify(store.get_zero_vote_alerts())


@e14_data_bp.route('/confidence-distribution', methods=['GET'])
def get_confidence_distribution():
    """Get histogram of OCR confidence values."""
    store = get_e14_json_store()
    bins = request.args.get('bins', 10, type=int)
    return jsonify(store.get_confidence_distribution(bins=bins))


@e14_data_bp.route('/votes-by-municipality', methods=['GET'])
def get_votes_by_municipality():
    """Get votes grouped by municipality."""
    if e14_sql_reader.is_sql_mode():
        return jsonify(e14_sql_reader.get_votes_by_municipality(
            departamento=request.args.get('departamento'),
        ))

    store = get_e14_json_store()
    dept = request.args.get('departamento')
    return jsonify(store.get_votes_by_municipality(departamento=dept))


@e14_data_bp.route('/pmsn-alerts', methods=['GET'])
def get_pmsn_alerts():
    """Expose PMSN business-rule alerts and summaries."""
    if e14_sql_reader.is_sql_mode():
        return jsonify(e14_sql_reader.get_pmsn_alerts())

    store = get_e14_json_store()
    payload = collect_pmsn_alerts(store)
    return jsonify(payload)


@e14_data_bp.route('/summary/by-dept', methods=['GET'])
def get_summary_by_dept():
    """Get summary grouped by department and corporacion."""
    store = get_e14_json_store()
    return jsonify(store.get_summary_by_dept())
@e14_data_bp.route('/validate/<int:form_id>', methods=['GET'])
def validate_single_form(form_id: int):
    """Run full validation on a single form and return diagnostics."""
    store = get_e14_json_store()
    store._ensure_loaded()
    form = store._forms_by_id.get(form_id)
    if not form:
        return jsonify({'error': 'Form not found'}), 404

    validation = validate_form(form, auto_correct=False)
    return jsonify({
        'form_id': form_id,
        'mesa_id': form.get('mesa_id', ''),
        'filename': form.get('filename', ''),
        'validation': validation,
    })


@e14_data_bp.route('/validate/batch', methods=['POST'])
def validate_batch_forms():
    """Run validation on all loaded forms and return summary."""
    store = get_e14_json_store()
    store._ensure_loaded()
    auto_correct = request.args.get('auto_correct', 'false').lower() == 'true'
    summary = validate_batch(store._forms, auto_correct=auto_correct)
    # Remove per-form results to keep response compact; use /validate/<id>
    summary.pop('results', None)
    return jsonify(summary)


def _find_pdf_path(filename: str, form: dict) -> Optional[str]:
    """Search for a PDF in multiple locations under E14_RAW_DIR.

    Strategy:
      1) flat/ directory (resolve symlinks) — original scraper filenames.
      2) Direct path {CORP}/{DEPT}/{MUNI}/{filename} using form metadata — O(1), correct.
      3) Decode scraper filename segments to build the local naming
         convention: {CORP}/{DEPT}/{MUNI}/{puesto}_{zona}_mesa{mesa}.pdf
    """
    from config import Config
    raw_dir = Config.E14_RAW_DIR

    # 0) uploaded/ — PDFs uploaded directly via the web UI
    candidate = os.path.join(raw_dir, 'uploaded', filename)
    if os.path.isfile(candidate):
        return candidate

    # 1) flat/ directory (resolve symlinks)
    flat_dir = os.path.realpath(os.path.join(raw_dir, 'flat'))
    candidate = os.path.join(flat_dir, filename)
    if os.path.isfile(candidate):
        return candidate

    # 2) Direct path using dept/muni from form — filenames like N_NN_mesaNNN.pdf are
    #    NOT unique across municipalities (e.g. 0_00_mesa003.pdf exists in 800+ dirs),
    #    so a tree walk would return the wrong acta. Use the form's location instead.
    dept = (form.get('departamento') or '').strip()
    muni = (form.get('municipio') or '').strip()
    if dept and muni:
        for subdir in ('SEN', 'CAM'):
            candidate = os.path.join(raw_dir, subdir, dept, muni, filename)
            if os.path.isfile(candidate):
                return candidate

    # 3) Decode scraper filename to local naming convention
    #    Scraper format: {id}_E14_{CORP}_X_{dd}_{ddd}_{ccc}_XX_{pp}_{mmm}_X_XXX.pdf
    #    Local format:   {CORP}/{DEPT}/{MUNI}/{int(ccc)}_{int(pp)}_mesa{int(mmm):03d}.pdf
    base = filename.replace('.pdf', '')
    parts = base.split('_')
    # Need at least 12 segments: id,E14,corp,X,d1,d2,puesto,XX,zona,mesa,X,XXX
    if len(parts) >= 12:
        corp_code = parts[2]  # SEN or CAM
        puesto_raw = parts[6]
        zona_raw = parts[8]
        mesa_raw = parts[9]
        try:
            puesto_int = int(puesto_raw)
            zona_int = int(zona_raw)
            mesa_int = int(mesa_raw)
        except ValueError:
            return None

        corp_dir = 'SEN' if corp_code.upper().startswith('SEN') else 'CAM'
        dept = (form.get('departamento') or '').strip()
        muni = (form.get('municipio') or '').strip()
        local_name = f'{puesto_int}_{zona_int:02d}_mesa{mesa_int:03d}.pdf'

        if dept and muni:
            candidate = os.path.join(raw_dir, corp_dir, dept, muni, local_name)
            if os.path.isfile(candidate):
                return candidate

        # Fallback: dept missing (OCR noise) — scan all dept dirs for muni
        if not dept and muni:
            corp_root = os.path.join(raw_dir, corp_dir)
            if os.path.isdir(corp_root):
                for dept_name in os.listdir(corp_root):
                    candidate = os.path.join(
                        corp_root, dept_name, muni, local_name,
                    )
                    if os.path.isfile(candidate):
                        return candidate

    return None


def _pdf_not_found_html(message: str) -> str:
    """Return a styled HTML page for PDF-not-found (rendered in iframe)."""
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
body {{ font-family: 'Source Sans 3', sans-serif; display: flex;
       align-items: center; justify-content: center; height: 100vh;
       margin: 0; background: #F7F4EE; color: #444; text-align: center; }}
.box {{ padding: 2rem; max-width: 400px; }}
h3 {{ margin: 0 0 0.5rem; font-size: 1.1rem; }}
p {{ font-size: 0.85rem; color: #777; }}
</style></head><body><div class="box">
<h3>PDF no disponible</h3>
<p>{message}</p>
</div></body></html>"""


@e14_data_bp.route('/pdf/<int:form_id>', methods=['GET'])
def get_form_pdf(form_id: int):
    """Serve the original E-14 PDF file for a given form."""
    store = get_e14_json_store()
    form = store.get_form_detail(form_id)
    if not form:
        return _pdf_not_found_html('Formulario no encontrado en el sistema.'), 404, {'Content-Type': 'text/html'}

    filename = form.get('filename', '')
    if not filename:
        return _pdf_not_found_html('Este formulario no tiene PDF asociado.'), 404, {'Content-Type': 'text/html'}

    doc_id = str(form.get('extraction_id') or '').strip() or _extract_doc_id_from_filename(filename)
    blob_response = _stream_pdf_from_blob(doc_id, filename_hint=filename)
    if blob_response is not None:
        return blob_response

    pdf_path = _find_pdf_path(filename, form)

    if not pdf_path:
        return _pdf_not_found_html(
            f'El archivo <b>{filename}</b> no se encontro en el directorio de PDFs. '
            'No fue posible recuperarlo ni localmente ni desde Blob con el document_id.'
        ), 404, {'Content-Type': 'text/html'}

    return send_from_directory(
        os.path.dirname(pdf_path),
        os.path.basename(pdf_path),
        mimetype='application/pdf',
    )


def _run_ocr_job(job_id: str, tmp_path: str, filename: str) -> None:
    """Background thread: run Azure OCR and update job state."""
    from config import Config
    from services.azure_ocr_service import process_pdf_file
    from services.e14_constants import compute_full_sum

    job = _upload_jobs[job_id]
    try:
        form = process_pdf_file(tmp_path)
        form['filename'] = filename

        results_dir = Config.E14_AZURE_RESULTS_DIR
        os.makedirs(results_dir, exist_ok=True)
        stem = os.path.splitext(filename)[0]
        out_path = os.path.join(results_dir, f"{stem}_azure.json")
        with open(out_path, 'w', encoding='utf-8') as fh:
            json.dump(form, fh, ensure_ascii=False, indent=2)

        store = get_e14_json_store()
        loaded_form = store.inject_form(out_path)

        anomaly_class = 'filtered_out'
        form_id = None
        validation: dict = {}
        if loaded_form:
            form_id = loaded_form['id']
            validation = loaded_form.get('validation', {})
            conf = loaded_form.get('ocr_confidence', 1.0)
            total = loaded_form.get('total_votos', 0) or 0
            blancos = loaded_form.get('votos_blancos') or 0
            nulos = loaded_form.get('votos_nulos') or 0
            no_marc = loaded_form.get('votos_no_marcados') or 0
            full_sum = compute_full_sum(loaded_form['partidos'], blancos, nulos, no_marc)
            has_arith = full_sum > 0 and total > 0 and abs(full_sum - total) > ARITH_WARN_TOL
            pre_gate = validation.get('pre_validation_gate', {})
            is_extraction_failure = not pre_gate.get('passed', True)
            checks = validation.get('checks', [])
            has_repeated = any(
                c.get('rule') == 'STAT-04' and not c.get('passed') for c in checks
            )
            if is_extraction_failure:
                anomaly_class = 'extraction_failure'
            elif has_repeated:
                anomaly_class = 'ocr_mapping_error'
            elif has_arith:
                anomaly_class = 'arithmetic_error'
            elif conf < ANOMALY_HIGH_RISK_THRESHOLD:
                anomaly_class = 'high_risk'
            elif conf < ANOMALY_NEEDS_REVIEW_DEFAULT:
                anomaly_class = 'needs_review'
            else:
                anomaly_class = 'healthy'

        job.update({
            'status': 'done',
            'success': True,
            'filename': filename,
            'out_path': out_path,
            'form_id': form_id,
            'anomaly_class': anomaly_class,
            'in_dashboard': anomaly_class not in ('healthy', 'filtered_out'),
            'form': {
                'departamento': form.get('departamento'),
                'municipio': form.get('municipio'),
                'mesa': form.get('mesa'),
                'corporacion': form.get('corporacion'),
                'total_votos': form.get('total_votos'),
                'confidence': form.get('confidence'),
                'warnings': form.get('warnings', []),
                'partidos': form.get('partidos', []),
            },
            'validation': validation,
        })
    except Exception as exc:
        logger.error("OCR job %s failed for %s: %s", job_id, filename, exc)
        job.update({'status': 'error', 'error': str(exc)})
    finally:
        shutil.rmtree(os.path.dirname(tmp_path), ignore_errors=True)


@e14_data_bp.route('/azure/upload', methods=['POST'])
def azure_upload():
    """
    Start async Azure OCR for an uploaded PDF.
    Returns immediately with a job_id; poll /azure/job/<job_id> for result.
    """
    from config import Config

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded. Use field name "file".'}), 400

    uploaded = request.files['file']
    if not uploaded.filename or not uploaded.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are accepted.'}), 400

    filename = uploaded.filename
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, filename)
    uploaded.save(tmp_path)

    # Persist PDF to raw/uploaded/ so _find_pdf_path() can serve it later
    upload_dir = os.path.join(Config.E14_RAW_DIR, 'uploaded')
    os.makedirs(upload_dir, exist_ok=True)
    shutil.copy2(tmp_path, os.path.join(upload_dir, filename))

    import time as _time
    job_id = str(uuid.uuid4())
    _upload_jobs[job_id] = {'status': 'processing', 'filename': filename, 'started_at': _time.time()}

    t = threading.Thread(target=_run_ocr_job, args=(job_id, tmp_path, filename), daemon=True)
    t.start()

    return jsonify({'job_id': job_id, 'status': 'processing', 'filename': filename}), 202


_OCR_JOB_TIMEOUT_S = 300  # 5 min max

@e14_data_bp.route('/azure/job/<job_id>', methods=['GET'])
def azure_job_status(job_id: str):
    """Poll the status of an async OCR upload job."""
    import time as _time
    job = _upload_jobs.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    # Auto-expire jobs stuck in processing beyond timeout
    if job.get('status') == 'processing':
        elapsed = _time.time() - job.get('started_at', _time.time())
        if elapsed > _OCR_JOB_TIMEOUT_S:
            job.update({'status': 'error', 'error': f'Timeout — Azure no respondió en {_OCR_JOB_TIMEOUT_S}s'})
    return jsonify(job)


@e14_data_bp.route('/azure/inject-json', methods=['POST'])
def azure_inject_json():
    """
    Inject a pre-computed Azure OCR JSON into the store.

    Accepts multipart/form-data with:
        file: *_azure.json (required)

    Bypasses OCR re-run. Useful when Azure OCR was run externally
    or when a known-good JSON needs to replace current store data.
    """
    import json as json_lib
    from services.azure_ocr_service import normalize_to_form
    from services.e14_json_store import get_e14_json_store
    from services.e14_validator import validate_form as validate_e14_form

    if 'file' not in request.files:
        return jsonify({'error': 'No file. Use field name "file".'}), 400

    uploaded_file = request.files['file']
    if not uploaded_file.filename or not uploaded_file.filename.lower().endswith('.json'):
        return jsonify({'error': 'Only JSON files are accepted.'}), 400

    filename = uploaded_file.filename
    tmp_dir = tempfile.mkdtemp()
    tmp_path = os.path.join(tmp_dir, filename)
    try:
        uploaded_file.save(tmp_path)
        with open(tmp_path, 'r', encoding='utf-8') as fh:
            raw = json_lib.load(fh)
    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify({'error': f'Cannot read JSON: {exc}'}), 400

    # Support both pre-normalized (_azure.json from CASTOR) and raw Azure /results output
    if 'partidos' in raw:
        form = raw
    else:
        form = normalize_to_form(raw, filename=filename, document_id=filename)

    # Save JSON to disk for persistence
    from config import Config as _Config
    results_dir = _Config.E14_AZURE_RESULTS_DIR
    os.makedirs(results_dir, exist_ok=True)
    stem = filename.replace('.json', '').replace('_azure', '')
    out_path = os.path.join(results_dir, f"{stem}_azure.json")
    with open(out_path, 'w', encoding='utf-8') as fh:
        json_lib.dump(form, fh, ensure_ascii=False, indent=2)

    shutil.rmtree(tmp_dir, ignore_errors=True)

    # Inject into store (inject_form latest-wins — replaces duplicate mesa)
    store = get_e14_json_store()
    injected = store.inject_form(out_path)
    if injected is None:
        return jsonify({'error': 'Form filtered out (not municipio objetivo or load failed)'}), 422

    validation = validate_e14_form(injected)
    injected['validation'] = validation

    return jsonify({
        'success': True,
        'form_id': injected.get('id'),
        'filename': filename,
        'out_path': out_path,
        'in_dashboard': True,
        'form': injected,
    })


@e14_data_bp.route('/azure/process', methods=['POST'])
def azure_process():
    """
    Process E-14 PDFs via Azure OCR and load them into the JSON store.

    Body (JSON, all optional):
        limit (int): max PDFs to process, capped at 20 (default 5)

    Returns JSON with processed/errors counts and per-file results.
    """
    import glob
    import json
    from config import Config
    from services.azure_ocr_service import process_pdf_file

    body = request.get_json() or {}
    limit = min(int(body.get("limit", 5)), 20)

    flat_dir    = Config.E14_FLAT_DIR
    results_dir = Config.E14_AZURE_RESULTS_DIR

    all_pdfs = sorted(glob.glob(os.path.join(flat_dir, "*.pdf")))
    paths = [p for p in all_pdfs if "(1)" not in os.path.basename(p)][:limit]

    if not paths:
        return jsonify({
            "processed": 0, "errors": 0, "forms": [], "failed": [],
            "message": f"No PDFs found in {flat_dir}",
        })

    os.makedirs(results_dir, exist_ok=True)
    processed, errors = [], []

    for path in paths:
        basename = os.path.basename(path)
        try:
            form = process_pdf_file(path)
            stem = os.path.splitext(basename)[0]
            out_path = os.path.join(results_dir, f"{stem}_azure.json")
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(form, fh, ensure_ascii=False, indent=2)
            processed.append({"filename": stem, "out": out_path})
        except Exception as exc:
            logger.error("Azure OCR failed for %s: %s", basename, exc)
            errors.append({"filename": basename, "error": str(exc)})

    # Force store reload on next request
    get_e14_json_store()._loaded_at = 0

    return jsonify({
        "processed": len(processed),
        "errors":    len(errors),
        "forms":     processed,
        "failed":    errors,
    })
