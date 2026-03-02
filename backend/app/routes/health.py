"""
Health check endpoint with SLA compliance metrics.
"""
from flask import Blueprint, jsonify, current_app
from datetime import datetime
from typing import Dict, Any
import logging
import time
try:
    import psutil
except Exception:  # pragma: no cover - optional dependency in dev
    psutil = None
import os

from utils.circuit_breaker import (
    get_openai_circuit_breaker,
    CircuitState
)

logger = logging.getLogger(__name__)

# SLA Definitions
SLA_TARGETS = {
    "latency_p95_ms": 3000,      # <3s para analisis
    "availability_percent": 99.5, # 99.5% uptime
    "error_rate_percent": 1.0,    # <1% errores
    "db_response_ms": 100,        # DB debe responder <100ms
}

# Metrics storage (in production, use Prometheus)
_metrics = {
    "requests_total": 0,
    "requests_failed": 0,
    "latencies": [],
    "start_time": datetime.utcnow()
}

health_bp = Blueprint('health', __name__)


def _check_database() -> Dict[str, Any]:
    """Check database connectivity with latency measurement."""
    try:
        db_service = current_app.extensions.get("database_service")
        if not db_service:
            return {"status": "unavailable", "error": "Database service not initialized"}

        # Try to execute a simple query with timing
        session = db_service.get_session()
        try:
            start = time.time()
            session.execute("SELECT 1")
            session.commit()
            latency_ms = (time.time() - start) * 1000

            sla_compliant = latency_ms < SLA_TARGETS["db_response_ms"]
            return {
                "status": "ok",
                "latency_ms": round(latency_ms, 2),
                "sla_target_ms": SLA_TARGETS["db_response_ms"],
                "sla_compliant": sla_compliant
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {"status": "error", "error": str(e)}
        finally:
            session.close()
    except Exception as e:
        logger.error(f"Database health check exception: {e}")
        return {"status": "error", "error": str(e)}


def _check_cache() -> Dict[str, Any]:
    """Report cache backend status for this profile."""
    return {
        "status": "ok",
        "backend": "memory",
        "message": "Memory cache enabled"
    }


def _check_system_resources() -> Dict[str, Any]:
    """Check system resources (CPU, Memory, Disk)."""
    try:
        if psutil is None:
            return {"status": "unavailable", "error": "psutil not installed"}
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "cpu_percent": cpu_percent,
            "memory": {
                "total_gb": round(memory.total / (1024**3), 2),
                "used_gb": round(memory.used / (1024**3), 2),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "used_gb": round(disk.used / (1024**3), 2),
                "percent": round(disk.percent, 1)
            },
            "warnings": []
        }
    except Exception as e:
        return {"error": str(e)}


def _calculate_sla_compliance() -> Dict[str, Any]:
    """Calculate current SLA compliance metrics."""
    uptime_seconds = (datetime.utcnow() - _metrics["start_time"]).total_seconds()
    uptime_hours = uptime_seconds / 3600

    total_requests = _metrics["requests_total"]
    failed_requests = _metrics["requests_failed"]

    error_rate = (failed_requests / total_requests * 100) if total_requests > 0 else 0
    availability = 100 - error_rate

    # Calculate p95 latency from stored latencies
    latencies = _metrics["latencies"][-1000:]  # Last 1000 requests
    p95_latency = 0
    if latencies:
        sorted_latencies = sorted(latencies)
        p95_idx = int(len(sorted_latencies) * 0.95)
        p95_latency = sorted_latencies[p95_idx] if p95_idx < len(sorted_latencies) else sorted_latencies[-1]

    return {
        "uptime_hours": round(uptime_hours, 2),
        "requests_total": total_requests,
        "requests_failed": failed_requests,
        "error_rate_percent": round(error_rate, 3),
        "availability_percent": round(availability, 3),
        "latency_p95_ms": round(p95_latency, 2),
        "sla_targets": SLA_TARGETS,
        "compliance": {
            "availability": availability >= SLA_TARGETS["availability_percent"],
            "error_rate": error_rate <= SLA_TARGETS["error_rate_percent"],
            "latency": p95_latency <= SLA_TARGETS["latency_p95_ms"] if p95_latency > 0 else True
        }
    }


def _check_circuit_breakers() -> Dict[str, Any]:
    """Check circuit breaker states."""
    openai_cb = get_openai_circuit_breaker()
    return {
        "openai": {
            "state": openai_cb.state.value,
            "failure_count": openai_cb.failure_count,
            "last_failure": openai_cb.last_failure_time.isoformat() if openai_cb.last_failure_time else None
        }
    }


@health_bp.route('/health', methods=['GET'])
def health():
    """
    Comprehensive health check endpoint.
    
    Returns:
        Status, timestamp, and health checks for DB/cache/circuit breakers
    """
    db_check = _check_database()
    cache_check = _check_cache()
    circuit_breakers = _check_circuit_breakers()

    # Overall status: degraded only when critical dependencies fail.
    overall_status = "ok"
    if db_check.get("status") != "ok":
        overall_status = "degraded"

    # Check if any circuit breakers are open
    if circuit_breakers["openai"]["state"] == CircuitState.OPEN.value:
        overall_status = "degraded"

    response = {
        'status': overall_status,
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'CASTOR ELECCIONES API',
        'version': '1.0.0',
        'checks': {
            'database': db_check,
            'cache': cache_check,
            'circuit_breakers': circuit_breakers
        }
    }

    # Return 200 for ok/degraded, 503 for critical failures
    status_code = 200 if overall_status in ("ok", "degraded") else 503
    return jsonify(response), status_code



@health_bp.route('/health/deep', methods=['GET'])
def deep_health():
    """
    Deep health check that tests external service connectivity.
    WARNING: This endpoint makes actual API calls - use sparingly.
    """
    from config import Config

    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {}
    }

    # Check OpenAI API key presence
    results["checks"]["openai"] = {
        "configured": bool(Config.OPENAI_API_KEY),
        "model": Config.OPENAI_MODEL,
        "circuit_breaker": get_openai_circuit_breaker().get_state()
    }

    # Check Database
    results["checks"]["database"] = _check_database()

    # Check cache backend
    results["checks"]["cache"] = _check_cache()

    # Overall status
    all_ok = (
        results["checks"]["database"].get("status") == "ok" and
        results["checks"]["openai"]["configured"]
    )

    results["status"] = "ok" if all_ok else "degraded"

    return jsonify(results), 200 if all_ok else 503


@health_bp.route('/health/ready', methods=['GET'])
def readiness():
    """Kubernetes-style readiness probe."""
    db_check = _check_database()
    if db_check.get("status") != "ok":
        return jsonify({"ready": False, "reason": "database unavailable"}), 503
    return jsonify({"ready": True}), 200


@health_bp.route('/health/live', methods=['GET'])
def liveness():
    """Kubernetes-style liveness probe."""
    return jsonify({"alive": True, "timestamp": datetime.utcnow().isoformat()}), 200


@health_bp.route('/health/sla', methods=['GET'])
def sla_metrics():
    """
    SLA compliance metrics endpoint.

    Returns current SLA compliance status and metrics.
    Useful for monitoring dashboards and alerting.
    """
    sla_data = _calculate_sla_compliance()
    system_resources = _check_system_resources()

    response = {
        "timestamp": datetime.utcnow().isoformat(),
        "sla": sla_data,
        "system": system_resources,
        "overall_sla_compliant": all(sla_data["compliance"].values())
    }

    return jsonify(response), 200


@health_bp.route('/health/full', methods=['GET'])
def full_health():
    """
    Complete health status with all checks and SLA metrics.

    This is the most comprehensive endpoint for monitoring.
    """
    db_check = _check_database()
    cache_check = _check_cache()
    circuit_breakers = _check_circuit_breakers()
    system_resources = _check_system_resources()
    sla_compliance = _calculate_sla_compliance()

    # Determine overall status
    overall_status = "ok"
    issues = []

    if db_check.get("status") != "ok":
        overall_status = "critical"
        issues.append("Database unavailable")

    if circuit_breakers["openai"]["state"] == CircuitState.OPEN.value:
        overall_status = "degraded" if overall_status != "critical" else overall_status
        issues.append("OpenAI circuit breaker OPEN")

    # Check SLA compliance
    if not all(sla_compliance["compliance"].values()):
        issues.append("SLA targets not met")

    # Check system resources
    if system_resources.get("memory", {}).get("percent", 0) > 90:
        issues.append("High memory usage (>90%)")
    if system_resources.get("cpu_percent", 0) > 90:
        issues.append("High CPU usage (>90%)")
    if system_resources.get("disk", {}).get("percent", 0) > 90:
        issues.append("High disk usage (>90%)")

    response = {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "service": "CASTOR ELECCIONES API",
        "version": os.environ.get("APP_VERSION", "1.0.0"),
        "environment": os.environ.get("FLASK_ENV", "production"),
        "issues": issues,
        "checks": {
            "database": db_check,
            "cache": cache_check,
            "circuit_breakers": circuit_breakers
        },
        "system": system_resources,
        "sla": sla_compliance
    }

    status_code = 200 if overall_status == "ok" else (503 if overall_status == "critical" else 200)
    return jsonify(response), status_code


def record_request_metric(latency_ms: float, success: bool = True):
    """
    Record a request metric for SLA tracking.
    Call this from middleware or decorators.
    """
    _metrics["requests_total"] += 1
    if not success:
        _metrics["requests_failed"] += 1
    _metrics["latencies"].append(latency_ms)
    # Keep only last 10000 latencies to avoid memory issues
    if len(_metrics["latencies"]) > 10000:
        _metrics["latencies"] = _metrics["latencies"][-5000:]
