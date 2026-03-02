"""
CASTOR Electoral - Metrics Implementation
Basado en SLOs y QAS definidos.

Compatible con Prometheus, StatsD, y CloudWatch.
"""
import functools
import logging
import time
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Métricas Backend (In-Memory para MVP, Prometheus/StatsD en producción)
# =============================================================================

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


class MetricsRegistry:
    """
    Registry de métricas para CASTOR Electoral.
    En producción, reemplazar con prometheus_client o similar.
    """

    def __init__(self):
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._labels: Dict[str, Dict[str, str]] = {}

    def inc(self, name: str, value: float = 1, labels: Optional[Dict[str, str]] = None):
        """Incrementa un counter."""
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value
        self._labels[key] = labels or {}

    def set(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Establece un gauge."""
        key = self._make_key(name, labels)
        self._gauges[key] = value
        self._labels[key] = labels or {}

    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Registra un valor en un histogram."""
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._labels[key] = labels or {}

        # Limitar tamaño de histograma en memoria
        if len(self._histograms[key]) > 10000:
            self._histograms[key] = self._histograms[key][-5000:]

    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Crea key único para métrica con labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Obtiene valor de counter."""
        key = self._make_key(name, labels)
        return self._counters.get(key, 0)

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Obtiene valor de gauge."""
        key = self._make_key(name, labels)
        return self._gauges.get(key, 0)

    def get_histogram_percentile(
        self, name: str, percentile: float, labels: Optional[Dict[str, str]] = None
    ) -> Optional[float]:
        """Obtiene percentil de histogram."""
        key = self._make_key(name, labels)
        values = self._histograms.get(key, [])
        if not values:
            return None
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def export_all(self) -> Dict[str, Any]:
        """Exporta todas las métricas."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                k: {
                    "count": len(v),
                    "p50": self.get_histogram_percentile(k.split("{")[0], 50),
                    "p95": self.get_histogram_percentile(k.split("{")[0], 95),
                    "p99": self.get_histogram_percentile(k.split("{")[0], 99),
                }
                for k, v in self._histograms.items()
            },
            "timestamp": datetime.utcnow().isoformat(),
        }


# Singleton global
_registry: Optional[MetricsRegistry] = None


def get_metrics_registry() -> MetricsRegistry:
    """Obtiene el registry global de métricas."""
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry


# =============================================================================
# Métricas de Ingesta (QAS L1)
# =============================================================================

def track_ingestion(func: Callable) -> Callable:
    """
    Decorator para trackear métricas de ingesta.

    Registra:
    - castor_ingestion_duration_seconds
    - castor_ingestion_requests_total
    - castor_ingestion_errors_total
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        registry = get_metrics_registry()
        start_time = time.time()
        status_code = "200"
        error_type = None

        try:
            result = func(*args, **kwargs)

            # Extraer status code del resultado si es posible
            if hasattr(result, '__iter__') and len(result) == 2:
                _, status_code = result
                status_code = str(status_code)

            return result

        except Exception as e:
            status_code = "500"
            error_type = type(e).__name__
            raise

        finally:
            duration = time.time() - start_time
            labels = {"status_code": status_code}

            registry.observe("castor_ingestion_duration_seconds", duration, labels)
            registry.inc("castor_ingestion_requests_total", 1, labels)

            if error_type:
                registry.inc("castor_ingestion_errors_total", 1, {"error_type": error_type})

    return wrapper


@contextmanager
def measure_ingestion(copy_type: str = "unknown", department: str = "unknown"):
    """
    Context manager para medir ingesta.

    Uso:
        with measure_ingestion(copy_type="DELEGADOS", department="11"):
            # código de ingesta
    """
    registry = get_metrics_registry()
    start_time = time.time()
    labels = {"copy_type": copy_type, "department": department}

    try:
        yield
        registry.inc("castor_ingestion_requests_total", 1, {**labels, "status_code": "200"})
    except Exception as e:
        registry.inc("castor_ingestion_requests_total", 1, {**labels, "status_code": "500"})
        registry.inc("castor_ingestion_errors_total", 1, {"error_type": type(e).__name__})
        raise
    finally:
        duration = time.time() - start_time
        registry.observe("castor_ingestion_duration_seconds", duration, labels)


# =============================================================================
# Métricas de OCR (QAS L2, S1)
# =============================================================================

def track_ocr_processing(func: Callable) -> Callable:
    """
    Decorator para trackear métricas de OCR.

    Registra:
    - castor_ocr_duration_seconds
    - castor_ocr_confidence
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        registry = get_metrics_registry()
        start_time = time.time()

        try:
            result = func(*args, **kwargs)

            # Registrar confidence si está disponible
            if hasattr(result, 'overall_confidence'):
                registry.observe(
                    "castor_ocr_confidence",
                    result.overall_confidence,
                    {"field_type": "overall"}
                )

            return result

        finally:
            duration = time.time() - start_time
            registry.observe("castor_ocr_duration_seconds", duration)

    return wrapper


class OCRMetrics:
    """Helper para métricas de OCR."""

    @staticmethod
    def set_queue_depth(depth: int, priority: str = "normal"):
        """Actualiza profundidad de cola OCR."""
        registry = get_metrics_registry()
        registry.set("castor_ocr_queue_depth", depth, {"priority": priority})

    @staticmethod
    def set_workers_active(count: int, pool: str = "default"):
        """Actualiza workers activos."""
        registry = get_metrics_registry()
        registry.set("castor_ocr_workers_active", count, {"worker_pool": pool})

    @staticmethod
    def track_anthropic_request(model: str, status: str, cost_usd: float, tokens: int):
        """Registra request a Anthropic."""
        registry = get_metrics_registry()
        registry.inc("castor_anthropic_requests_total", 1, {"model": model, "status": status})
        registry.inc("castor_anthropic_cost_usd", cost_usd, {"model": model})
        registry.inc("castor_anthropic_tokens_total", tokens, {"model": model})

    @staticmethod
    def track_needs_review(field_type: str, reason: str):
        """Registra campo que necesita revisión."""
        registry = get_metrics_registry()
        registry.inc("castor_ocr_needs_review_total", 1, {
            "field_type": field_type,
            "reason": reason
        })


# =============================================================================
# Métricas de Validación (QAS I2, I3)
# =============================================================================

class ValidationMetrics:
    """Helper para métricas de validación."""

    @staticmethod
    def track_validation(rule_key: str, passed: bool, severity: str):
        """Registra ejecución de validación."""
        registry = get_metrics_registry()
        registry.inc("castor_validation_executions_total", 1, {
            "rule_key": rule_key,
            "result": "passed" if passed else "failed",
            "severity": severity
        })

    @staticmethod
    def track_alert(alert_type: str, severity: str, department: str):
        """Registra alerta generada."""
        registry = get_metrics_registry()
        registry.inc("castor_validation_alerts_total", 1, {
            "alert_type": alert_type,
            "severity": severity,
            "department": department
        })

    @staticmethod
    def track_reconciliation(scope: str, duration_seconds: float, has_discrepancy: bool):
        """Registra reconciliación."""
        registry = get_metrics_registry()
        registry.observe("castor_reconciliation_duration_seconds", duration_seconds, {"scope": scope})
        if has_discrepancy:
            registry.inc("castor_reconciliation_discrepancies_total", 1, {"scope": scope})


# =============================================================================
# Métricas de Dashboard/War Room (QAS L3)
# =============================================================================

class DashboardMetrics:
    """Helper para métricas de dashboard."""

    @staticmethod
    def track_load_time(view: str, duration_seconds: float, user_role: str = "operator"):
        """Registra tiempo de carga de vista."""
        registry = get_metrics_registry()
        registry.observe("castor_dashboard_load_seconds", duration_seconds, {
            "view": view,
            "user_role": user_role
        })

    @staticmethod
    def track_cache(hit: bool, cache_type: str, key_pattern: str):
        """Registra hit/miss de caché."""
        registry = get_metrics_registry()
        metric = "castor_cache_hits_total" if hit else "castor_cache_misses_total"
        registry.inc(metric, 1, {"cache_type": cache_type, "key_pattern": key_pattern})

    @staticmethod
    def set_active_users(count: int, role: str = "operator", view: str = "main"):
        """Actualiza usuarios activos."""
        registry = get_metrics_registry()
        registry.set("castor_dashboard_users_active", count, {
            "user_role": role,
            "view": view
        })


# =============================================================================
# Métricas de Base de Datos (QAS A3, S2)
# =============================================================================

class DatabaseMetrics:
    """Helper para métricas de base de datos."""

    @staticmethod
    def set_connections(active: int, pool: str = "default", state: str = "active"):
        """Actualiza conexiones de BD."""
        registry = get_metrics_registry()
        registry.set("castor_db_connections_active", active, {"pool": pool, "state": state})

    @staticmethod
    def track_query(query_type: str, table: str, duration_seconds: float):
        """Registra query a BD."""
        registry = get_metrics_registry()
        registry.observe("castor_db_query_duration_seconds", duration_seconds, {
            "query_type": query_type,
            "table": table
        })

    @staticmethod
    def set_replication_lag(lag_seconds: float, replica: str = "replica-1"):
        """Actualiza lag de replicación."""
        registry = get_metrics_registry()
        registry.set("castor_db_replication_lag_seconds", lag_seconds, {"replica": replica})

    @staticmethod
    def track_write(table: str, operation: str, batch_size: int = 1):
        """Registra escritura a BD."""
        registry = get_metrics_registry()
        registry.inc("castor_db_writes_total", 1, {"table": table, "operation": operation})
        registry.observe("castor_db_write_batch_size", batch_size, {"table": table})


# =============================================================================
# Métricas de Seguridad (QAS Sec1, Sec2)
# =============================================================================

class SecurityMetrics:
    """Helper para métricas de seguridad."""

    @staticmethod
    def track_auth_attempt(result: str, method: str = "jwt"):
        """Registra intento de autenticación."""
        registry = get_metrics_registry()
        registry.inc("castor_auth_attempts_total", 1, {"result": result, "method": method})

    @staticmethod
    def track_authz_check(resource: str, action: str, allowed: bool):
        """Registra verificación de autorización."""
        registry = get_metrics_registry()
        result = "allowed" if allowed else "denied"
        registry.inc("castor_authz_checks_total", 1, {
            "resource": resource,
            "action": action,
            "result": result
        })
        if not allowed:
            registry.inc("castor_authz_denied_total", 1, {
                "resource": resource,
                "action": action
            })

    @staticmethod
    def track_rate_limit_hit(endpoint: str, user_id: str):
        """Registra hit de rate limit."""
        registry = get_metrics_registry()
        registry.inc("castor_rate_limit_hits_total", 1, {
            "endpoint": endpoint,
            "user_id": user_id[:8] + "..."  # Truncar por privacidad
        })

    @staticmethod
    def track_audit_event(action: str, entity_type: str, actor_role: str):
        """Registra evento de auditoría."""
        registry = get_metrics_registry()
        registry.inc("castor_audit_events_total", 1, {
            "action": action,
            "entity_type": entity_type,
            "actor_role": actor_role
        })


# =============================================================================
# Métricas Electorales (Negocio)
# =============================================================================

class ElectoralMetrics:
    """Helper para métricas electorales."""

    @staticmethod
    def track_form_received(department: str, municipality: str, corporacion: str, copy_type: str):
        """Registra formulario recibido."""
        registry = get_metrics_registry()
        registry.inc("castor_forms_received_total", 1, {
            "department": department,
            "municipality": municipality,
            "corporacion": corporacion,
            "copy_type": copy_type
        })

    @staticmethod
    def track_form_processed(department: str, municipality: str, corporacion: str, status: str):
        """Registra formulario procesado."""
        registry = get_metrics_registry()
        registry.inc("castor_forms_processed_total", 1, {
            "department": department,
            "municipality": municipality,
            "corporacion": corporacion,
            "status": status
        })

    @staticmethod
    def set_coverage(department: str, municipality: str, corporacion: str, percentage: float):
        """Actualiza porcentaje de cobertura."""
        registry = get_metrics_registry()
        registry.set("castor_coverage_percentage", percentage, {
            "department": department,
            "municipality": municipality,
            "corporacion": corporacion
        })

    @staticmethod
    def track_votes_tallied(department: str, corporacion: str, ballot_option_type: str, votes: int):
        """Registra votos contabilizados."""
        registry = get_metrics_registry()
        registry.inc("castor_votes_tallied_total", votes, {
            "department": department,
            "corporacion": corporacion,
            "ballot_option_type": ballot_option_type
        })

    @staticmethod
    def track_electoral_alert(alert_type: str, severity: str, department: str):
        """Registra alerta electoral."""
        registry = get_metrics_registry()
        registry.inc("castor_electoral_alerts_total", 1, {
            "alert_type": alert_type,
            "severity": severity,
            "department": department
        })

    @staticmethod
    def set_open_alerts(alert_type: str, severity: str, count: int):
        """Actualiza alertas abiertas."""
        registry = get_metrics_registry()
        registry.set("castor_electoral_alerts_open", count, {
            "alert_type": alert_type,
            "severity": severity
        })


# =============================================================================
# Endpoint para exportar métricas
# =============================================================================

def get_metrics_endpoint():
    """
    Retorna endpoint handler para exponer métricas.

    Uso en Flask:
        @app.route('/metrics')
        def metrics():
            return get_metrics_endpoint()()
    """
    def handler():
        registry = get_metrics_registry()
        metrics_data = registry.export_all()

        # Formato Prometheus-like
        lines = []
        for name, value in metrics_data["counters"].items():
            lines.append(f"{name} {value}")
        for name, value in metrics_data["gauges"].items():
            lines.append(f"{name} {value}")
        for name, hist_data in metrics_data["histograms"].items():
            base_name = name.split("{")[0]
            labels = name[len(base_name):] if "{" in name else ""
            lines.append(f"{base_name}_count{labels} {hist_data['count']}")
            if hist_data['p50']:
                lines.append(f"{base_name}_p50{labels} {hist_data['p50']:.4f}")
            if hist_data['p95']:
                lines.append(f"{base_name}_p95{labels} {hist_data['p95']:.4f}")
            if hist_data['p99']:
                lines.append(f"{base_name}_p99{labels} {hist_data['p99']:.4f}")

        return "\n".join(lines), 200, {"Content-Type": "text/plain"}

    return handler
