"""
Routes para la Cola de Incidentes del War Room.
Persistencia real en SQLite (sin datos demo).
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from flask import Blueprint, jsonify, request

from app.schemas.incidents import (
    IncidentCreate, IncidentListResponse, IncidentStatsResponse,
    IncidentStats, IncidentSeverity, IncidentStatus,
    IncidentAssignRequest, IncidentResolveRequest, IncidentEscalateRequest,
    INCIDENT_CONFIG, WarRoomKPIsResponse
)
from utils.rate_limiter import limiter
from services.incident_store import (
    create_incident as store_create_incident,
    list_incidents as store_list_incidents,
    get_incident as store_get_incident,
    update_incident as store_update_incident,
    stats as store_stats,
)
from services.e14_data_service import E14DataService

logger = logging.getLogger(__name__)

incidents_bp = Blueprint('incidents', __name__)
limiter.exempt(incidents_bp)


@incidents_bp.route('', methods=['GET'])
def list_incidents():
    """
    List incidents with filters.

    Query params:
        incident_type (optional): Filter by type
        status (optional): Filter by status
        limit (optional): Max results
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        incident_type = request.args.get('incident_type')
        status = request.args.get('status')

        types = [t.strip() for t in incident_type.split(',')] if incident_type else None
        statuses = [s.strip() for s in status.split(',')] if status else None

        incidents, counts = store_list_incidents(status=statuses, incident_type=types, limit=limit)
        response = IncidentListResponse(
            incidents=incidents,
            total=counts["total"],
            open_count=counts["open_count"],
            p0_count=counts["p0_count"],
            p1_count=counts["p1_count"],
        )
        return jsonify(response.dict())
    except Exception as e:
        logger.error(f"Error listing incidents: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@incidents_bp.route('/<int:incident_id>', methods=['GET'])
def get_incident(incident_id: int):
    """Get a single incident by ID."""
    try:
        incident = store_get_incident(incident_id)
        if not incident:
            return jsonify({"success": False, "error": "Incident not found"}), 404
        return jsonify({"success": True, "incident": incident})
    except Exception as e:
        logger.error(f"Error getting incident: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@incidents_bp.route('', methods=['POST'])
def create_incident():
    """Create a new incident."""
    try:
        data = request.get_json() or {}
        req = IncidentCreate(**data)

        config = INCIDENT_CONFIG.get(req.incident_type, {"default_severity": IncidentSeverity.P2, "sla_minutes": 30})
        severity = req.severity or config.get('default_severity', IncidentSeverity.P2)
        incident = store_create_incident({
            "incident_type": req.incident_type.value,
            "mesa_id": req.mesa_id,
            "dept_code": req.dept_code,
            "dept_name": req.dept_name,
            "muni_code": req.muni_code,
            "muni_name": req.muni_name,
            "puesto": req.puesto,
            "description": req.description,
            "severity": severity.value if isinstance(severity, IncidentSeverity) else str(severity),
            "ocr_confidence": req.ocr_confidence,
            "delta_value": req.delta_value,
            "evidence": req.evidence,
        }, dedupe=True)

        return jsonify({"success": True, "incident": incident}), 201
    except Exception as e:
        logger.error(f"Error creating incident: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@incidents_bp.route('/<int:incident_id>/assign', methods=['POST'])
def assign_incident(incident_id: int):
    """Assign an incident to a user."""
    try:
        data = request.get_json() or {}
        req = IncidentAssignRequest(**data)

        incident = store_get_incident(incident_id)
        if not incident:
            return jsonify({"success": False, "error": "Incident not found"}), 404

        updated = store_update_incident(incident_id, {
            "status": IncidentStatus.ASSIGNED.value,
            "assigned_to": req.user_id,
            "assigned_at": datetime.utcnow().isoformat(),
            "resolution_notes": req.notes or incident.get("resolution_notes"),
        })
        return jsonify({"success": True, "incident": updated})
    except Exception as e:
        logger.error(f"Error assigning incident: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@incidents_bp.route('/<int:incident_id>/resolve', methods=['POST'])
def resolve_incident(incident_id: int):
    """Resolve an incident."""
    try:
        data = request.get_json() or {}
        req = IncidentResolveRequest(**data)

        incident = store_get_incident(incident_id)
        if not incident:
            return jsonify({"success": False, "error": "Incident not found"}), 404

        status = IncidentStatus.FALSE_POSITIVE.value if req.resolution.upper() == "FALSE_POSITIVE" else IncidentStatus.RESOLVED.value
        updated = store_update_incident(incident_id, {
            "status": status,
            "resolved_at": datetime.utcnow().isoformat(),
            "resolution_notes": req.notes,
        })
        return jsonify({"success": True, "incident": updated})
    except Exception as e:
        logger.error(f"Error resolving incident: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@incidents_bp.route('/<int:incident_id>/escalate', methods=['POST'])
def escalate_incident(incident_id: int):
    """Escalate an incident."""
    try:
        data = request.get_json() or {}
        req = IncidentEscalateRequest(**data)

        incident = store_get_incident(incident_id)
        if not incident:
            return jsonify({"success": False, "error": "Incident not found"}), 404

        updated = store_update_incident(incident_id, {
            "status": IncidentStatus.ESCALATED.value,
            "escalated_to_legal": 1 if req.to_legal else 0,
            "resolution_notes": f"ESCALADO: {req.reason}",
        })
        return jsonify({"success": True, "incident": updated})
    except Exception as e:
        logger.error(f"Error escalating incident: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@incidents_bp.route('/stats', methods=['GET'])
def get_incident_stats():
    """Get incident statistics."""
    try:
        stats = store_stats()
        response = IncidentStatsResponse(stats=IncidentStats(**stats))
        return jsonify(response.dict())
    except Exception as e:
        logger.error(f"Error getting incident stats: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


@incidents_bp.route('/war-room/kpis', methods=['GET'])
def get_war_room_kpis():
    """Get War Room KPIs and timeline progress."""
    try:
        data_service = E14DataService()
        stats = data_service.get_stats()

        mesas_total = stats.get("total_forms", 0)
        mesas_testigo = stats.get("ocr_completed", 0)
        mesas_rnec = 0
        mesas_reconciliadas = 0

        p0_count = store_stats().get("by_severity", {}).get("P0", 0)
        cobertura = ((mesas_testigo + mesas_rnec) / mesas_total * 100) if mesas_total > 0 else 0

        kpis = {
            "mesas_total": mesas_total,
            "mesas_testigo": mesas_testigo,
            "mesas_rnec": mesas_rnec,
            "mesas_reconciliadas": mesas_reconciliadas,
            "incidentes_p0": p0_count,
            "cobertura_pct": round(cobertura, 1),
            "testigo_pct": round(mesas_testigo / mesas_total * 100, 1) if mesas_total > 0 else 0,
            "rnec_pct": round(mesas_rnec / mesas_total * 100, 1) if mesas_total > 0 else 0,
            "reconciliadas_pct": round(mesas_reconciliadas / mesas_total * 100, 1) if mesas_total > 0 else 0,
            "last_rnec_update": None,
            "last_testigo_update": datetime.utcnow().isoformat() if mesas_testigo > 0 else None,
        }

        timeline = [
            {
                "source": "WITNESS",
                "label": "Testigo",
                "processed": mesas_testigo,
                "total": mesas_total,
                "percentage": kpis["testigo_pct"],
                "last_update": kpis["last_testigo_update"]
            },
            {
                "source": "OFFICIAL",
                "label": "RNEC",
                "processed": mesas_rnec,
                "total": mesas_total,
                "percentage": kpis["rnec_pct"],
                "last_update": kpis["last_rnec_update"]
            },
            {
                "source": "RECONCILED",
                "label": "Reconciliadas",
                "processed": mesas_reconciliadas,
                "total": mesas_total,
                "percentage": kpis["reconciliadas_pct"],
                "last_update": None
            }
        ]

        return jsonify(WarRoomKPIsResponse(kpis=kpis, timeline=timeline).dict())
    except Exception as e:
        logger.error(f"Error getting war room KPIs: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
