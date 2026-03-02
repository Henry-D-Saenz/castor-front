"""
Campaign Team Dashboard API — War Room + E-14 live data.
"""
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Optional

from flask import Blueprint, jsonify, request, current_app

from utils.rate_limiter import limiter
from services import e14_sql_reader

import logging
logger = logging.getLogger(__name__)
_e14_live_cache: dict = {}
_E14_LIVE_CACHE_TTL_SECONDS = 20


def _html_to_pdf(html_string: str) -> Optional[bytes]:
    """Convierte HTML a PDF usando weasyprint en un subprocess con DYLD path correcto."""
    _WEASYPRINT_SCRIPT = (
        'import sys; from weasyprint import HTML; '
        'sys.stdout.buffer.write(HTML(string=sys.stdin.read()).write_pdf())'
    )
    try:
        env = {**os.environ, 'DYLD_FALLBACK_LIBRARY_PATH': '/opt/homebrew/lib'}
        result = subprocess.run(
            [sys.executable, '-c', _WEASYPRINT_SCRIPT],
            input=html_string.encode('utf-8'),
            capture_output=True,
            timeout=60,
            env=env,
        )
        if result.returncode == 0 and result.stdout:
            logger.info('PDF generado via subprocess: %d bytes', len(result.stdout))
            return result.stdout
        logger.warning('weasyprint subprocess error: %s', result.stderr[:300].decode('utf-8', errors='replace'))
        # Fallback puro Python cuando weasyprint no está disponible en runtime.
        return _html_to_pdf_fallback(html_string)
    except Exception as e:
        logger.warning('_html_to_pdf failed: %s', e)
        return _html_to_pdf_fallback(html_string)


def _html_to_pdf_fallback(html_string: str) -> Optional[bytes]:
    """Fallback simple HTML->PDF sin dependencias nativas (usa fpdf2)."""
    try:
        from fpdf import FPDF
    except Exception as e:
        logger.warning('fpdf2 no disponible para fallback PDF: %s', e)
        return None

    try:
        txt = re.sub(r'(?is)<(script|style).*?>.*?</\\1>', ' ', html_string or '')
        txt = re.sub(r'(?i)<br\\s*/?>', '\n', txt)
        txt = re.sub(r'(?i)</p\\s*>', '\n\n', txt)
        txt = re.sub(r'<[^>]+>', ' ', txt)
        txt = unescape(txt)
        txt = re.sub(r'[ \\t]+', ' ', txt)
        lines = [ln.strip() for ln in txt.splitlines()]
        clean = '\n'.join(ln for ln in lines if ln)

        pdf = FPDF(unit='mm', format='A4')
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font('Helvetica', size=10)

        # Core fonts de FPDF soportan latin-1; reemplazar chars fuera de rango.
        for para in clean.split('\n'):
            safe = para.encode('latin-1', errors='replace').decode('latin-1')
            pdf.multi_cell(0, 5, safe)

        raw = pdf.output(dest='S')
        payload = raw.encode('latin-1') if isinstance(raw, str) else bytes(raw)
        logger.info('PDF fallback generado con fpdf2: %d bytes', len(payload))
        return payload if payload else None
    except Exception as e:
        logger.warning('fallback PDF failed: %s', e)
        return None


def _extract_doc_id(form: dict) -> str:
    """Resolve document_id from extraction_id or UUID filename stem."""
    doc_id = str(form.get('document_id') or '').strip()
    if doc_id:
        return doc_id
    doc_id = str(form.get('extraction_id') or '').strip()
    if doc_id:
        return doc_id
    fn = str(form.get('filename') or '').strip()
    stem = Path(fn).stem
    return stem if re.fullmatch(r'[0-9a-fA-F-]{36}', stem) else ''


def _load_e14_pdf_bytes(form: dict) -> tuple[Optional[str], Optional[bytes], str]:
    """Load E-14 PDF from local disk or Blob using document_id.

    Returns (filename, bytes, source) where source is local|blob|none.
    """
    fn = form.get('filename')
    if fn:
        search_dirs = [
            PDF_BASE_DIR,
            PROJECT_ROOT / 'data' / 'e14' / 'raw',
            PROJECT_ROOT / 'data' / 'e14_congreso_2022' / 'uploaded',
            PROJECT_ROOT / 'data' / 'e14_congreso_2022',
        ]
        for d in search_dirs:
            p = d / fn
            if p.exists():
                return fn, p.read_bytes(), 'local'

    doc_id = _extract_doc_id(form)
    if not doc_id:
        return None, None, 'none'

    try:
        from config import Config
        conn = (Config.AZURE_STORAGE_CONNECTION_STRING or '').strip()
        container = (Config.AZURE_STORAGE_CONTAINER_NAME or '').strip()
        if not conn or not container:
            return None, None, 'none'

        from azure.storage.blob import BlobServiceClient
        service = BlobServiceClient.from_connection_string(conn)
        container_client = service.get_container_client(container)
        prefix = f'{doc_id}/'
        blobs = [
            b for b in container_client.list_blobs(name_starts_with=prefix)
            if str(getattr(b, 'name', '')).lower().endswith('.pdf')
        ]
        if not blobs:
            return None, None, 'none'

        blob_item = sorted(
            blobs,
            key=lambda b: getattr(b, 'last_modified', None) or 0,
            reverse=True,
        )[0]
        blob_name = blob_item.name
        payload = container_client.download_blob(blob_name).readall()
        out_name = fn if fn and str(fn).lower().endswith('.pdf') else Path(blob_name).name
        return out_name, payload, 'blob'
    except Exception as e:
        logger.warning('No se pudo cargar PDF E-14 desde blob: %s', e)
        return None, None, 'none'

PROJECT_ROOT = Path(__file__).resolve().parents[3]
PDF_BASE_DIR = PROJECT_ROOT / "actas_e14_masivo" / "pdfs_congreso_2022"

PARTY_COLORS = [
    "#6366F1", "#8B5CF6", "#EC4899", "#EF4444", "#F59E0B",
    "#10B981", "#3B82F6", "#F97316", "#14B8A6", "#84CC16",
]

campaign_team_bp = Blueprint('campaign_team', __name__)
limiter.exempt(campaign_team_bp)


def _get_store():
    from services.e14_json_store import get_e14_json_store
    return get_e14_json_store()


def _pmsn_votes(partidos: list) -> int:
    total = 0
    for p in partidos:
        raw = (p.get('party_name') or '').upper()
        name = ''.join(
            ch for ch in unicodedata.normalize('NFD', raw)
            if unicodedata.category(ch) != 'Mn'
        )
        if 'NUEVO LIBERALISMO' in name:
            continue
        if 'SALVACION' in name or 'PMSN' in name:
            total += p.get('votes', 0)
    return total


# ── E-14 Live ────────────────────────────────────────────────────────────────

@campaign_team_bp.route('/e14-live', methods=['GET'])
def get_e14_live_data():
    """Real E-14 data from OCR JSON store."""
    try:
        limit = request.args.get('limit', 100, type=int)
        corp = request.args.get('corporacion')
        dept = request.args.get('departamento')
        muni = request.args.get('municipio')
        risk = request.args.get('risk')

        cache_key = f"e14_live|l={limit}|c={corp}|d={dept}|m={muni}|r={risk}|sql={e14_sql_reader.is_sql_mode()}"
        now = time.time()
        cached = _e14_live_cache.get(cache_key)
        if cached and (now - cached.get("ts", 0) <= _E14_LIVE_CACHE_TTL_SECONDS):
            return jsonify(cached["payload"])

        if e14_sql_reader.is_sql_mode():
            filtered = e14_sql_reader.get_forms_full(
                limit=limit,
                corporacion=corp,
                departamento=dept,
                municipio=muni,
            )
            if risk:
                r = risk.lower()
                if r == 'high':
                    filtered = [f for f in filtered if f["ocr_confidence"] < 0.70]
                elif r == 'medium':
                    filtered = [f for f in filtered if 0.70 <= f["ocr_confidence"] < 0.85]
                elif r == 'low':
                    filtered = [f for f in filtered if f["ocr_confidence"] >= 0.85]

            total_votos = sum(f["total_votos"] for f in filtered)
            avg_conf = sum(f["ocr_confidence"] for f in filtered) / max(len(filtered), 1)
            pmsn_total = sum(_pmsn_votes(f.get('partidos', [])) for f in filtered)
            stats = {
                'total_forms': len(filtered),
                'total_votes': total_votos,
                'total_blancos': sum(f["votos_blancos"] or 0 for f in filtered),
                'total_nulos': sum(f["votos_nulos"] or 0 for f in filtered),
                'avg_confidence': round(avg_conf, 3),
                'pmsn_total_votes': pmsn_total,
            }

            party_raw = e14_sql_reader.get_party_totals(
                limit=30,
                departamento=dept,
                corporacion=corp,
            )
            party_summary = [
                {**p, 'id': i + 1, 'color': PARTY_COLORS[i % len(PARTY_COLORS)], 'trend': 'stable'}
                for i, p in enumerate(party_raw)
            ]

            forms = [
                {
                    'id': f['id'],
                    'mesa_id': f['mesa_id'],
                    'filename': f['filename'],
                    'total_votos': f['total_votos'],
                    'pmsn_votes': _pmsn_votes(f.get('partidos', [])),
                    'processed_at': f.get('processed_at'),
                    'overall_confidence': round(f['ocr_confidence'], 3),
                    'source': 'e14_sql',
                    'header': {
                        'election_name': 'CONGRESO 2022',
                        'election_date': '13 DE MARZO DE 2022',
                        'corporacion': f['corporacion'],
                        'departamento': f['departamento'],
                        'municipio': f['municipio'],
                        'zona': f['zona_cod'],
                        'puesto': f['puesto_cod'],
                        'mesa': f['mesa_num'],
                    },
                    'resumen': {
                        'total_votos_validos': f['total_votos'],
                        'votos_blanco': f['votos_blancos'],
                        'votos_nulos': f['votos_nulos'],
                    },
                    'partidos': f.get('partidos', []),
                }
                for f in filtered[:limit]
            ]

            payload = {
                'success': True,
                'source': 'e14_sql',
                'stats': stats,
                'party_summary': party_summary,
                'forms': forms,
                'top_departamentos': [],
                'total_forms': stats['total_forms'],
                'forms_returned': len(forms),
                'total_votes': stats['total_votes'],
                'total_parties': len(party_summary),
                'timestamp': datetime.utcnow().isoformat(),
            }
            _e14_live_cache[cache_key] = {"ts": now, "payload": payload}
            return jsonify(payload)

        store = _get_store()
        filtered = store._filter_forms(corporacion=corp, departamento=dept, municipio=muni)

        if risk:
            r = risk.lower()
            if r == 'high':
                filtered = [f for f in filtered if f["ocr_confidence"] < 0.70]
            elif r == 'medium':
                filtered = [f for f in filtered if 0.70 <= f["ocr_confidence"] < 0.85]
            elif r == 'low':
                filtered = [f for f in filtered if f["ocr_confidence"] >= 0.85]

        total_votos = sum(f["total_votos"] for f in filtered)
        avg_conf = sum(f["ocr_confidence"] for f in filtered) / max(len(filtered), 1)
        pmsn_total = sum(_pmsn_votes(f.get('partidos', [])) for f in filtered)

        stats = {
            'total_forms': len(filtered),
            'total_votes': total_votos,
            'total_blancos': sum(f["votos_blancos"] or 0 for f in filtered),
            'total_nulos': sum(f["votos_nulos"] or 0 for f in filtered),
            'avg_confidence': round(avg_conf, 3),
            'pmsn_total_votes': pmsn_total,
        }

        party_raw = store.get_party_totals(limit=30, departamento=dept, corporacion=corp)
        party_summary = [
            {**p, 'id': i + 1, 'color': PARTY_COLORS[i % len(PARTY_COLORS)], 'trend': 'stable'}
            for i, p in enumerate(party_raw)
        ]

        forms = [
            {
                'id': f['id'],
                'mesa_id': f['mesa_id'],
                'filename': f['filename'],
                'total_votos': f['total_votos'],
                'pmsn_votes': _pmsn_votes(f.get('partidos', [])),
                'processed_at': f.get('processed_at'),
                'overall_confidence': round(f['ocr_confidence'], 3),
                'source': 'e14_json',
                'header': {
                    'election_name': 'CONGRESO 2022',
                    'election_date': '13 DE MARZO DE 2022',
                    'corporacion': f['corporacion'],
                    'departamento': f['departamento'],
                    'municipio': f['municipio'],
                    'zona': f['zona_cod'],
                    'puesto': f['puesto_cod'],
                    'mesa': f['mesa_num'],
                },
                'resumen': {
                    'total_votos_validos': f['total_votos'],
                    'votos_blanco': f['votos_blancos'],
                    'votos_nulos': f['votos_nulos'],
                },
                'partidos': f.get('partidos', []),
            }
            for f in filtered[:limit]
        ]

        dept_counts: dict = {}
        for f in filtered:
            d = f['departamento']
            if d not in dept_counts:
                dept_counts[d] = {'mesas': 0, 'votos': 0}
            dept_counts[d]['mesas'] += 1
            dept_counts[d]['votos'] += f['total_votos']
        top_dept = sorted(dept_counts.items(), key=lambda x: x[1]['mesas'], reverse=True)[:10]

        payload = {
            'success': True,
            'source': 'e14_json',
            'stats': stats,
            'party_summary': party_summary,
            'forms': forms,
            'top_departamentos': [
                {'departamento': d, 'mesas': v['mesas'], 'votos': v['votos']}
                for d, v in top_dept
            ],
            'total_forms': stats['total_forms'],
            'forms_returned': len(forms),
            'total_votes': stats['total_votes'],
            'total_parties': len(party_summary),
            'timestamp': datetime.utcnow().isoformat(),
        }
        _e14_live_cache[cache_key] = {"ts": now, "payload": payload}
        return jsonify(payload)
    except Exception as e:
        logger.error("e14-live error: %s", e, exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Mesa Detail ───────────────────────────────────────────────────────────────

@campaign_team_bp.route('/mesa/<mesa_id>/detail', methods=['GET'])
def get_mesa_detail(mesa_id: str):
    """Detail for a single mesa pulled from the E-14 JSON store."""
    try:
        mesa_id = str(mesa_id or "").strip()
        if not mesa_id:
            return jsonify({"success": False, "error": "Mesa id is required"}), 400

        if e14_sql_reader.is_sql_mode():
            form = (
                e14_sql_reader.get_form_detail(int(mesa_id))
                if mesa_id.isdigit()
                else e14_sql_reader.get_form_by_identifier(mesa_id)
            )
            if not form:
                return jsonify({"success": False, "error": "Mesa not found"}), 404

            conf = form.get('ocr_confidence', 0)
            if conf >= 0.85:
                status = "VALIDATED"
            elif conf >= 0.70:
                status = "NEEDS_REVIEW"
            else:
                status = "HIGH_RISK"

            detail = {
                "mesa_id": form.get('mesa_id', mesa_id),
                "header": {
                    "dept_name": form.get('departamento', '--'),
                    "muni_name": form.get('municipio', '--'),
                    "puesto": form.get('puesto_cod', '--'),
                    "mesa_number": form.get('mesa_num', '--'),
                    "zona": form.get('zona_cod', '--'),
                    "corporacion": form.get('corporacion', '--'),
                },
                "status": status,
                "overall_confidence": round(float(conf), 3),
                "processed_at": form.get('processed_at'),
                "pdf_url": None,
                "resumen": {
                    "total_votos": form.get('total_votos', 0),
                    "votos_blancos": form.get('votos_blancos'),
                    "votos_nulos": form.get('votos_nulos'),
                },
                "partidos": form.get('partidos', []),
                "validation": form.get('validation', {}),
            }
            return jsonify({"success": True, "detail": detail})

        store = _get_store()
        store._ensure_loaded()
        form = store._forms_by_id.get(int(mesa_id)) if mesa_id.isdigit() else None

        if not form:
            for f in store._forms:
                if f.get('mesa_id') == mesa_id:
                    form = f
                    break

        # Fallback: allow document/extraction identifiers (exact or prefix).
        if not form:
            mesa_id_flat = mesa_id.replace('-', '')
            for f in store._forms:
                extraction_id = str(f.get('extraction_id') or "").strip()
                document_id = str(f.get('document_id') or "").strip()
                extraction_id_flat = extraction_id.replace('-', '')
                document_id_flat = document_id.replace('-', '')
                if mesa_id in (extraction_id, document_id):
                    form = f
                    break
                if extraction_id.startswith(mesa_id) or document_id.startswith(mesa_id):
                    form = f
                    break
                if mesa_id_flat and (
                    mesa_id_flat in (extraction_id_flat, document_id_flat)
                    or extraction_id_flat.startswith(mesa_id_flat)
                    or document_id_flat.startswith(mesa_id_flat)
                ):
                    form = f
                    break

        if not form:
            return jsonify({"success": False, "error": "Mesa not found"}), 404

        conf = form.get('ocr_confidence', 0)
        if conf >= 0.85:
            status = "VALIDATED"
        elif conf >= 0.70:
            status = "NEEDS_REVIEW"
        else:
            status = "HIGH_RISK"

        pdf_filename = form.get('filename')
        pdf_url = None
        if pdf_filename and (PDF_BASE_DIR / pdf_filename).exists():
            pdf_url = f"/api/e14-data/pdf/{pdf_filename}"

        detail = {
            "mesa_id": mesa_id,
            "header": {
                "dept_name": form.get('departamento', '--'),
                "muni_name": form.get('municipio', '--'),
                "puesto": form.get('puesto_cod', '--'),
                "mesa_number": form.get('mesa_num', '--'),
                "zona": form.get('zona_cod', '--'),
                "corporacion": form.get('corporacion', '--'),
            },
            "status": status,
            "overall_confidence": round(float(conf), 3),
            "processed_at": form.get('processed_at'),
            "pdf_url": pdf_url,
            "resumen": {
                "total_votos": form.get('total_votos', 0),
                "votos_blancos": form.get('votos_blancos'),
                "votos_nulos": form.get('votos_nulos'),
            },
            "partidos": form.get('partidos', []),
            "validation": form.get('validation', {}),
        }
        return jsonify({"success": True, "detail": detail})
    except Exception as e:
        logger.error("mesa detail error: %s", e, exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ── War Room (stub) ───────────────────────────────────────────────────────────

@campaign_team_bp.route('/war-room/stats', methods=['GET'])
def get_war_room_stats():
    try:
        if e14_sql_reader.is_sql_mode():
            s = e14_sql_reader.get_stats()
            n = int(s.get("total_forms", 0) or 0)
            return jsonify({
                "success": True,
                "stats": {
                    "total_mesas": n, "mesas_processed": n,
                    "processing_percentage": 100 if n else 0,
                    "total_votes": int(s.get("total_votos", 0) or 0),
                    "incidents_open": 0, "incidents_resolved": 0,
                }
            })

        store = _get_store()
        store._ensure_loaded()
        n = len(store._forms)
        return jsonify({
            "success": True,
            "stats": {
                "total_mesas": n, "mesas_processed": n,
                "processing_percentage": 100 if n else 0,
                "total_votes": sum(f["total_votos"] for f in store._forms),
                "incidents_open": 0, "incidents_resolved": 0,
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@campaign_team_bp.route('/war-room/progress', methods=['GET'])
def get_processing_progress():
    return jsonify({"success": True, "progress": {"processed": 0, "total": 0, "percentage": 0}})


@campaign_team_bp.route('/war-room/alerts', methods=['GET'])
def get_alerts():
    return jsonify({"success": True, "alerts": [], "total": 0})


@campaign_team_bp.route('/war-room/alerts/<int:alert_id>/assign', methods=['POST'])
def assign_alert(alert_id: int):
    return jsonify({"success": True, "alert_id": alert_id})


# ── Reports (stub) ────────────────────────────────────────────────────────────

@campaign_team_bp.route('/reports/votes-by-candidate', methods=['GET'])
def get_votes_by_candidate():
    try:
        store = _get_store()
        party_raw = store.get_party_totals(limit=20)
        candidates = [
            {"id": i + 1, "name": p["party_name"], "votes": p["total_votes"],
             "color": PARTY_COLORS[i % len(PARTY_COLORS)]}
            for i, p in enumerate(party_raw)
        ]
        return jsonify({"success": True, "candidates": candidates})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@campaign_team_bp.route('/reports/regional-trends', methods=['GET'])
def get_regional_trends():
    return jsonify({"success": True, "trends": []})


@campaign_team_bp.route('/summary', methods=['GET'])
def get_dashboard_summary():
    return jsonify({"success": True, "summary": {}})


# ── E-14 Cache ────────────────────────────────────────────────────────────────

@campaign_team_bp.route('/e14-cache/info', methods=['GET'])
def get_e14_cache_info():
    try:
        from services.e14_cache_service import get_e14_cache_service
        return jsonify({"success": True, **get_e14_cache_service().get_cache_info()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@campaign_team_bp.route('/e14-cache/clear', methods=['POST', 'DELETE'])
def clear_e14_cache():
    try:
        from services.e14_cache_service import get_e14_cache_service
        deleted = get_e14_cache_service().clear_all()
        return jsonify({"success": True, "deleted_count": deleted})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Envío impugnación por email ───────────────────────────────────────────────

@campaign_team_bp.route('/send-impugnacion', methods=['POST'])
def send_impugnacion():
    """Envía impugnación (PDF) + acta E-14 original (PDF) por Gmail SMTP."""
    import smtplib
    import os
    import io
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    data         = request.get_json(force=True) or {}
    destinatario = data.get('destinatario', '').strip()
    mesa_id      = data.get('mesa_id', 'MESA')
    incident_id  = data.get('incident_id')
    form_id_raw  = data.get('form_id')
    html_body    = data.get('html_doc', '')

    if not destinatario or '@' not in destinatario:
        return jsonify({'success': False, 'error': 'Destinatario inválido'}), 400
    if not html_body:
        return jsonify({'success': False, 'error': 'Documento vacío'}), 400

    SENDER   = os.getenv('IMPUGNAR_EMAIL', 'castorelecciones@gmail.com')
    PASSWORD = os.getenv('IMPUGNAR_APP_PASSWORD', 'tuii gsnv slcp zipl')

    # ── Convertir HTML → PDF (weasyprint subprocess) ─────────────────────────
    impug_pdf_bytes = _html_to_pdf(html_body)

    # ── Cargar PDF E-14 original (local o blob) ──────────────────────────────
    e14_pdf_name = None
    e14_pdf_bytes = None
    try:
        form = None

        if e14_sql_reader.is_sql_mode():
            if form_id_raw is not None and str(form_id_raw).strip().isdigit():
                form = e14_sql_reader.get_form_detail(int(str(form_id_raw).strip()))
            if not form and mesa_id:
                form = e14_sql_reader.get_form_by_identifier(str(mesa_id))
        else:
            store = _get_store()
            store._ensure_loaded()
            if form_id_raw is not None and str(form_id_raw).strip().isdigit():
                form = store._forms_by_id.get(int(str(form_id_raw).strip()))

            if not form and str(mesa_id).isdigit():
                form = store._forms_by_id.get(int(str(mesa_id)))

            if not form:
                for f in store._forms:
                    if f.get('mesa_id') == mesa_id:
                        form = f
                        break
        if form:
            e14_pdf_name, e14_pdf_bytes, e14_source = _load_e14_pdf_bytes(form)
            if e14_pdf_bytes:
                logger.info('PDF E-14 cargado para adjunto desde %s: %s', e14_source, e14_pdf_name)
    except Exception as e:
        logger.warning('No se pudo localizar PDF E-14: %s', e)

    # ── Cuerpo del correo ────────────────────────────────────────────────────
    adjuntos_desc = []
    if impug_pdf_bytes:
        adjuntos_desc.append(f'<li><code>impugnacion_{mesa_id}.pdf</code> — Recurso de Impugnación (listo para imprimir en A4)</li>')
    else:
        adjuntos_desc.append(f'<li><code>impugnacion_{mesa_id}.html</code> — Recurso de Impugnación (abrir en navegador)</li>')
    if e14_pdf_bytes:
        adjuntos_desc.append(f'<li><code>{e14_pdf_name}</code> — Formulario E-14 original escaneado</li>')

    cuerpo_html = f"""
<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#222;">
<p>Estimado(a),</p>
<p>Se adjuntan los documentos del <strong>Recurso de Impugnación</strong> generados por
<strong>CASTOR Elecciones</strong> para la mesa <strong>{mesa_id}</strong>:</p>
<ul>{''.join(adjuntos_desc)}</ul>
<p>El recurso de impugnación puede imprimirse en formato A4 para su radicación ante la
Comisión Escrutadora.</p>
<hr style="border:none;border-top:1px solid #ddd;margin:1rem 0;">
<p style="font-size:12px;color:#666;">
  Enviado por CASTOR Elecciones — Sistema de Inteligencia Electoral<br>
  Este correo fue generado automáticamente. No responder a este mensaje.
</p>
</body></html>
"""
    asunto = f'Recurso de Impugnación – Mesa {mesa_id} – CASTOR Elecciones'
    msg = MIMEMultipart('mixed')
    msg['From']    = f'CASTOR Elecciones <{SENDER}>'
    msg['To']      = destinatario
    msg['Subject'] = asunto
    msg.attach(MIMEText(cuerpo_html, 'html', 'utf-8'))

    # ── Adjunto 1: impugnación PDF o HTML ────────────────────────────────────
    if impug_pdf_bytes:
        adj1 = MIMEBase('application', 'pdf')
        adj1.set_payload(impug_pdf_bytes)
        encoders.encode_base64(adj1)
        adj1.add_header('Content-Disposition', 'attachment', filename=f'impugnacion_{mesa_id}.pdf')
        msg.attach(adj1)
    else:
        adj1 = MIMEBase('text', 'html')
        adj1.set_payload(html_body.encode('utf-8'))
        encoders.encode_base64(adj1)
        adj1.add_header('Content-Disposition', 'attachment', filename=f'impugnacion_{mesa_id}.html')
        msg.attach(adj1)

    # ── Adjunto 2: PDF E-14 original ─────────────────────────────────────────
    if e14_pdf_bytes:
        adj2 = MIMEBase('application', 'pdf')
        adj2.set_payload(e14_pdf_bytes)
        encoders.encode_base64(adj2)
        adj2.add_header('Content-Disposition', 'attachment', filename=e14_pdf_name)
        msg.attach(adj2)
        logger.info('Adjuntando PDF E-14: %s', e14_pdf_name)

    attachments_sent = []
    if impug_pdf_bytes:
        attachments_sent.append(f'impugnacion_{mesa_id}.pdf')
    else:
        attachments_sent.append(f'impugnacion_{mesa_id}.html')
    if e14_pdf_bytes:
        attachments_sent.append(e14_pdf_name)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(SENDER, PASSWORD)
            smtp.sendmail(SENDER, destinatario, msg.as_string())
        logger.info(
            'Impugnación enviada a %s mesa=%s incident_id=%s form_id=%s adjuntos=%s',
            destinatario,
            mesa_id,
            incident_id,
            form_id_raw,
            attachments_sent,
        )
        return jsonify({
            'success': True,
            'destinatario': destinatario,
            'mesa_id': mesa_id,
            'incident_id': incident_id,
            'form_id': form_id_raw,
            'attachments': attachments_sent,
        })
    except smtplib.SMTPAuthenticationError:
        logger.error('SMTP auth error al enviar impugnación')
        return jsonify({'success': False, 'error': 'Error de autenticación SMTP'}), 500
    except Exception as exc:
        logger.error('Error enviando impugnación: %s', exc)
        return jsonify({'success': False, 'error': str(exc)}), 500


# ── Health ────────────────────────────────────────────────────────────────────

@campaign_team_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "success": True, "service": "campaign-team-dashboard",
        "timestamp": datetime.utcnow().isoformat()
    })
