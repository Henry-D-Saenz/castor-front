"""
Routes para el módulo geoespacial del War Room.
Endpoints para mapa choropleth y estadísticas por departamento.
"""
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

from flask import Blueprint, jsonify, request, current_app

from services.e14_json_store import get_e14_json_store
from services import e14_sql_reader
from utils.rate_limiter import limiter

logger = logging.getLogger(__name__)

geography_bp = Blueprint('geography', __name__)

# Exempt from rate limiting - dashboard makes many parallel calls
limiter.exempt(geography_bp)

# Cache for GeoJSON data
_geojson_cache = None
_geojson_simplified_cache = None
_choropleth_cache: Dict[str, Dict] = {}
_CHOROPLETH_TTL_SECONDS = 30


def _perpendicular_distance(point: List[float], start: List[float], end: List[float]) -> float:
    """Distance from point to line segment."""
    x0, y0 = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return ((x0 - x1) ** 2 + (y0 - y1) ** 2) ** 0.5
    t = ((x0 - x1) * dx + (y0 - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    px = x1 + t * dx
    py = y1 + t * dy
    return ((x0 - px) ** 2 + (y0 - py) ** 2) ** 0.5


def _rdp(coords: List[List[float]], epsilon: float) -> List[List[float]]:
    """Douglas-Peucker simplification."""
    if len(coords) < 3:
        return coords
    start = coords[0]
    end = coords[-1]
    max_dist = -1.0
    idx = -1
    for i in range(1, len(coords) - 1):
        dist = _perpendicular_distance(coords[i], start, end)
        if dist > max_dist:
            max_dist = dist
            idx = i
    if max_dist > epsilon and idx != -1:
        left = _rdp(coords[:idx + 1], epsilon)
        right = _rdp(coords[idx:], epsilon)
        return left[:-1] + right
    return [start, end]


def _simplify_ring(ring: List[List[float]], epsilon: float) -> List[List[float]]:
    if len(ring) < 6:
        return ring
    closed = ring[0] == ring[-1]
    work = ring[:-1] if closed else ring
    simp = _rdp(work, epsilon)
    if len(simp) < 3:
        simp = work[:3]
    if closed:
        simp = simp + [simp[0]]
    # Quantize to reduce payload size.
    return [[round(float(x), 4), round(float(y), 4)] for x, y in simp]


def _simplify_geometry(geometry: dict, epsilon: float = 0.01) -> dict:
    gtype = (geometry or {}).get("type")
    coords = (geometry or {}).get("coordinates")
    if not gtype or coords is None:
        return geometry
    if gtype == "Polygon":
        # Keep only outer ring for performance on dashboard map.
        outer = coords[0] if coords else []
        return {"type": "Polygon", "coordinates": [_simplify_ring(outer, epsilon)]}
    if gtype == "MultiPolygon":
        polys = []
        for poly in coords:
            outer = poly[0] if poly else []
            polys.append([_simplify_ring(outer, epsilon)])
        return {"type": "MultiPolygon", "coordinates": polys}
    return geometry

# DANE code -> normalized department name (matching E14 store)
DANE_TO_DEPT: Dict[str, str] = {
    "05": "ANTIOQUIA", "08": "ATLANTICO", "11": "BOGOTA",
    "13": "BOLIVAR", "15": "BOYACA", "17": "CALDAS",
    "18": "CAQUETA", "19": "CAUCA", "20": "CESAR",
    "23": "CORDOBA", "25": "CUNDINAMARCA", "27": "CHOCO",
    "41": "HUILA", "44": "LA GUAJIRA", "47": "MAGDALENA",
    "50": "META", "52": "NARINO", "54": "NORTE DE SANTANDER",
    "63": "QUINDIO", "66": "RISARALDA", "68": "SANTANDER",
    "70": "SUCRE", "73": "TOLIMA", "76": "VALLE DEL CAUCA",
    "81": "ARAUCA", "85": "CASANARE", "86": "PUTUMAYO",
    "88": "SAN ANDRES", "91": "AMAZONAS", "94": "GUAINIA",
    "95": "GUAVIARE", "97": "VAUPES", "99": "VICHADA",
}


def load_geojson():
    """Load Colombia departments GeoJSON."""
    global _geojson_cache

    if _geojson_cache is not None:
        return _geojson_cache

    try:
        # Find the static folder
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        project_root = os.path.dirname(app_dir)
        geojson_path = os.path.join(project_root, 'static', 'data', 'colombia-departments.geojson')

        if os.path.exists(geojson_path):
            with open(geojson_path, 'r', encoding='utf-8') as f:
                _geojson_cache = json.load(f)
                return _geojson_cache
        else:
            logger.warning(f"GeoJSON file not found at {geojson_path}")
            return None
    except Exception as e:
        logger.error(f"Error loading GeoJSON: {e}")
        return None


def load_geojson_simplified():
    """Load and simplify GeoJSON once for faster map rendering."""
    global _geojson_simplified_cache
    if _geojson_simplified_cache is not None:
        return _geojson_simplified_cache
    raw = load_geojson()
    if not raw:
        return None
    simplified = {"type": raw.get("type", "FeatureCollection"), "features": []}
    for feature in raw.get("features", []):
        simplified["features"].append({
            "type": "Feature",
            "properties": dict(feature.get("properties", {})),
            "geometry": _simplify_geometry(feature.get("geometry", {}), epsilon=0.01),
        })
    _geojson_simplified_cache = simplified
    return _geojson_simplified_cache


def get_e14_dept_metrics(
    dept_code: str,
    mode: str = 'coverage',
    sql_metrics_map: Optional[Dict[str, Dict]] = None,
) -> dict:
    """Get real metrics from E14 JSON store for a department."""
    dept_name = DANE_TO_DEPT.get(dept_code, "")

    if e14_sql_reader.is_sql_mode():
        metrics_map = sql_metrics_map if sql_metrics_map is not None else e14_sql_reader.get_department_metrics()
        m = metrics_map.get(dept_name, None)
        if not m:
            return {
                "dept_code": dept_code, "value": 0.0,
                "has_data": False,
                "mesas_total": 0, "mesas_ocr": 0, "mesas_anomalias": 0,
                "high_risk_count": 0, "medium_risk_count": 0,
                "low_risk_count": 0, "coverage_pct": 0.0,
                "incidents_open": 0, "incidents_p0": 0,
                "total_votos": 0, "votos_blancos": 0, "votos_nulos": 0,
                "avg_confidence": 0.0,
            }
        total_mesas = int(m["mesas_total"])
        high_risk = int(m["high_risk_count"])
        medium_risk = int(m["medium_risk_count"])
        if mode == 'coverage':
            value = 100.0
        elif mode == 'risk':
            value = round((high_risk + medium_risk * 0.5) / max(total_mesas, 1) * 100, 1)
        elif mode == 'votes':
            value = float(m["total_votos"])
        elif mode == 'discrepancy':
            value = round(high_risk / max(total_mesas, 1) * 100, 1)
        else:
            value = 0.0

        return {
            "dept_code": dept_code, "value": value,
            "has_data": True,
            "mesas_total": total_mesas, "mesas_ocr": int(m["mesas_ocr"]),
            "mesas_anomalias": int(m["mesas_anomalias"]),
            "high_risk_count": high_risk, "medium_risk_count": medium_risk,
            "low_risk_count": int(m["low_risk_count"]),
            "coverage_pct": 100.0,
            "incidents_open": high_risk + medium_risk,
            "incidents_p0": high_risk,
            "total_votos": int(m["total_votos"]),
            "votos_blancos": int(m["votos_blancos"]),
            "votos_nulos": int(m["votos_nulos"]),
            "avg_confidence": round(float(m["avg_confidence"]), 2),
        }

    store = get_e14_json_store()
    store._ensure_loaded()

    forms = store._filter_forms(departamento=dept_name) if dept_name else []
    total_mesas = len(forms)

    if total_mesas == 0:
        return {
            "dept_code": dept_code, "value": 0.0,
            "has_data": False,
            "mesas_total": 0, "mesas_ocr": 0, "mesas_anomalias": 0,
            "high_risk_count": 0, "medium_risk_count": 0,
            "low_risk_count": 0, "coverage_pct": 0.0,
            "incidents_open": 0, "incidents_p0": 0,
            "total_votos": 0, "votos_blancos": 0, "votos_nulos": 0,
            "avg_confidence": 0.0,
        }

    # Aggregate vote totals and confidence from forms (use `or 0` to handle null JSON values)
    total_votos = sum((f.get("total_votos") or 0) for f in forms)
    votos_blancos = sum((f.get("votos_blancos") or 0) for f in forms)
    votos_nulos = sum((f.get("votos_nulos") or 0) for f in forms)
    conf_sum = sum((f.get("ocr_confidence") or 0) for f in forms)
    avg_confidence = round(conf_sum / total_mesas, 2)

    anomalies = store.get_anomalies()
    dept_high = [a for a in anomalies.get("high_risk", [])
                 if a.get("departamento", "").upper() == dept_name]
    dept_review = [a for a in anomalies.get("needs_review", [])
                   if a.get("departamento", "").upper() == dept_name]
    dept_arith = [a for a in anomalies.get("arithmetic_errors", [])
                  if a.get("departamento", "").upper() == dept_name]

    high_risk = len(dept_high) + len(dept_arith)
    medium_risk = len(dept_review)

    if mode == 'coverage':
        value = 100.0  # All loaded forms are processed
    elif mode == 'risk':
        value = round(
            (high_risk + medium_risk * 0.5) / max(total_mesas, 1) * 100, 1
        )
    elif mode == 'votes':
        value = float(total_votos)
    elif mode == 'discrepancy':
        value = round(len(dept_arith) / max(total_mesas, 1) * 100, 1)
    else:
        value = 0.0

    return {
        "dept_code": dept_code, "value": value,
        "has_data": True,
        "mesas_total": total_mesas, "mesas_ocr": total_mesas,
        "mesas_anomalias": high_risk + medium_risk,
        "high_risk_count": high_risk, "medium_risk_count": medium_risk,
        "low_risk_count": total_mesas - high_risk - medium_risk,
        "coverage_pct": 100.0,
        "incidents_open": high_risk + medium_risk,
        "incidents_p0": high_risk,
        "total_votos": total_votos,
        "votos_blancos": votos_blancos,
        "votos_nulos": votos_nulos,
        "avg_confidence": avg_confidence,
    }


def get_color_for_value(value: float, mode: str) -> str:
    """Get color based on value and mode."""
    if mode == 'coverage':
        # Green (high) to Red (low)
        if value >= 80:
            return '#1E7D4F'  # Green
        elif value >= 60:
            return '#7CB342'  # Light green
        elif value >= 40:
            return '#F0C040'  # Yellow vivo
        elif value >= 20:
            return '#E87020'  # Naranja vivo
        else:
            return '#C0253A'  # Red

    elif mode == 'risk':
        # Red (high) to Green (low) - inverted
        if value >= 15:
            return '#C0253A'  # Red
        elif value >= 10:
            return '#E87020'  # Naranja vivo
        elif value >= 5:
            return '#F0C040'  # Yellow vivo
        elif value >= 2:
            return '#7CB342'  # Light green
        else:
            return '#1E7D4F'  # Green

    elif mode == 'discrepancy':
        # Orange (high) to Green (low)
        if value >= 10:
            return '#E87020'  # Naranja vivo
        elif value >= 5:
            return '#F0C040'  # Yellow vivo
        elif value >= 2:
            return '#7CB342'  # Light green
        else:
            return '#1E7D4F'  # Green

    else:  # votes
        # Purple scale for vote percentage
        if value >= 30:
            return '#7B1FA2'  # Dark purple
        elif value >= 20:
            return '#9C27B0'  # Purple
        elif value >= 15:
            return '#BA68C8'  # Light purple
        elif value >= 10:
            return '#CE93D8'  # Very light purple
        else:
            return '#E1BEE7'  # Pale purple


# ============================================================
# CHOROPLETH ENDPOINT
# ============================================================

@geography_bp.route('/choropleth', methods=['GET'])
def get_choropleth():
    """
    Get GeoJSON with metrics for choropleth map.

    Query params:
        mode: coverage | risk | discrepancy | votes (default: coverage)
        contest_id: Contest ID (optional)
        candidate_id: Candidate ID for votes mode (optional)

    Returns:
        GeoJSON with properties containing metrics and colors
    """
    try:
        mode = request.args.get('mode', 'coverage')
        contest_id = request.args.get('contest_id', type=int)

        # Fast path cache by mode for short bursts of repeated dashboard calls.
        now = time.time()
        cache_key = f"mode:{mode}"
        cached = _choropleth_cache.get(cache_key)
        if cached and (now - cached.get("ts", 0) <= _CHOROPLETH_TTL_SECONDS):
            return jsonify(cached["payload"])

        geojson = load_geojson_simplified()
        if not geojson:
            return jsonify({
                "success": False,
                "error": "GeoJSON data not available"
            }), 500

        # Build SQL metrics map once (avoid N+1 query pattern for 33 departments).
        sql_metrics_map = e14_sql_reader.get_department_metrics() if e14_sql_reader.is_sql_mode() else None

        # Collect metrics for all departments first
        features_with_metrics = []
        for feature in geojson.get('features', []):
            dept_code = feature['properties'].get('code')
            if not dept_code:
                continue
            metrics = get_e14_dept_metrics(dept_code, mode, sql_metrics_map=sql_metrics_map)
            features_with_metrics.append((feature, metrics))

        # For votes mode, normalize values to % of max for color scale
        if mode == 'votes':
            max_votes = max(
                (m['value'] for _, m in features_with_metrics), default=1
            ) or 1
            for _, metrics in features_with_metrics:
                if metrics['value'] > 0:
                    metrics['value_pct'] = round(
                        metrics['value'] / max_votes * 100, 1
                    )
                else:
                    metrics['value_pct'] = 0.0

        # Enrich features with metrics and colors
        enriched_features = []
        for feature, metrics in features_with_metrics:
            if mode == 'votes':
                color_val = metrics.get('value_pct', 0)
            else:
                color_val = metrics['value']
            color = get_color_for_value(color_val, mode)

            enriched_feature = {
                "type": "Feature",
                "properties": {
                    **feature['properties'],
                    "metrics": metrics,
                    "fill_color": color,
                    "value": metrics['value'],
                    "mode": mode
                },
                "geometry": feature['geometry']
            }
            enriched_features.append(enriched_feature)

        payload = {
            "success": True,
            "type": "FeatureCollection",
            "features": enriched_features,
            "mode": mode,
            "timestamp": datetime.utcnow().isoformat()
        }
        _choropleth_cache[cache_key] = {"ts": now, "payload": payload}
        return jsonify(payload)

    except Exception as e:
        logger.error(f"Error getting choropleth data: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# DEPARTMENT STATS ENDPOINT
# ============================================================

@geography_bp.route('/department/<dept_code>/stats', methods=['GET'])
def get_department_stats(dept_code: str):
    """Get statistics for a department from E14 JSON store."""
    try:
        geojson = load_geojson()
        dept_info = None
        if geojson:
            for feature in geojson.get('features', []):
                if feature['properties'].get('code') == dept_code:
                    dept_info = feature['properties']
                    break

        metrics = get_e14_dept_metrics(dept_code, 'coverage')
        dept_name = DANE_TO_DEPT.get(dept_code, "")
        if e14_sql_reader.is_sql_mode():
            top_parties = e14_sql_reader.get_party_totals(limit=5, departamento=dept_name) if dept_name else []
            munis = e14_sql_reader.get_municipios(dept_name) if dept_name else []
        else:
            store = get_e14_json_store()
            top_parties = store.get_party_totals(limit=5, departamento=dept_name) if dept_name else []
            munis = store.get_municipios(dept_name) if dept_name else []

        stats = {
            "dept_code": dept_code,
            "dept_name": dept_info.get('name') if dept_info else dept_name,
            "capital": dept_info.get('capital') if dept_info else None,
            **metrics,
            "top_parties": [
                {
                    "name": p["party_name"],
                    "votes": p["total_votes"],
                    "percentage": p["percentage"],
                }
                for p in top_parties
            ],
            "municipalities_processed": len(munis),
            "municipalities_total": len(munis),
            "last_update": datetime.utcnow().isoformat(),
        }

        return jsonify({"success": True, "stats": stats})

    except Exception as e:
        logger.error(f"Error getting department stats: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# DEPARTMENT INCIDENTS ENDPOINT
# ============================================================

@geography_bp.route('/department/<dept_code>/incidents', methods=['GET'])
def get_department_incidents(dept_code: str):
    """Get incidents for a department from E14 anomalies."""
    try:
        limit = request.args.get('limit', 10, type=int)
        dept_name = DANE_TO_DEPT.get(dept_code, "")
        if e14_sql_reader.is_sql_mode():
            incidents = e14_sql_reader.get_department_incidents(dept_name, limit=limit) if dept_name else []
            for inc in incidents:
                inc["dept_code"] = dept_code
                inc["dept_name"] = dept_name
            return jsonify({
                "success": True, "dept_code": dept_code,
                "dept_name": dept_name,
                "incidents": incidents[:limit],
                "total": len(incidents),
            })

        store = get_e14_json_store()
        anomalies = store.get_anomalies()

        severity_map = {
            "arithmetic_error": ("ARITHMETIC_FAIL", "P0"),
            "high_risk": ("OCR_LOW_CONF", "P1"),
            "needs_review": ("OCR_LOW_CONF", "P2"),
        }

        incidents = []
        for category in ("arithmetic_errors", "high_risk", "needs_review"):
            for form in anomalies.get(category, []):
                if dept_name and form.get("departamento", "").upper() != dept_name:
                    continue
                issue = form.get("issue", category.rstrip("s"))
                inc_type, severity = severity_map.get(issue, ("OTHER", "P3"))
                incidents.append({
                    "id": form["id"],
                    "incident_type": inc_type,
                    "severity": severity,
                    "status": "OPEN",
                    "mesa_id": form.get("mesa_id", ""),
                    "dept_code": dept_code,
                    "dept_name": form.get("departamento", dept_name),
                    "muni_name": form.get("municipio", ""),
                    "description": f"{issue}: conf={form.get('ocr_confidence', 0):.0%}",
                    "ocr_confidence": form.get("ocr_confidence"),
                    "created_at": datetime.utcnow().isoformat(),
                })

        sev_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        incidents.sort(key=lambda x: sev_order.get(x["severity"], 4))

        return jsonify({
            "success": True, "dept_code": dept_code,
            "dept_name": dept_name,
            "incidents": incidents[:limit],
            "total": len(incidents),
        })

    except Exception as e:
        logger.error(f"Error getting department incidents: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================
# HEALTH CHECK
# ============================================================

@geography_bp.route('/health', methods=['GET'])
def health_check():
    """Health check for geography API."""
    geojson = load_geojson()
    return jsonify({
        "success": True,
        "service": "geography",
        "geojson_loaded": geojson is not None,
        "departments_count": len(geojson.get('features', [])) if geojson else 0,
        "timestamp": datetime.utcnow().isoformat()
    })
