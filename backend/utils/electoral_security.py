"""
Seguridad específica para el módulo electoral.
- Rate limiting por costo
- Control de acceso por roles
- Tracking de uso de API
- Métricas de seguridad (QAS Sec1, Sec2)
"""
import logging
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, List, Optional
import enum
import threading

from flask import request, jsonify, g
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from config import Config

logger = logging.getLogger(__name__)


# Import de métricas (lazy para evitar circular imports)
def _get_security_metrics():
    """Obtiene SecurityMetrics de forma lazy."""
    try:
        from utils.metrics import SecurityMetrics
        return SecurityMetrics
    except ImportError:
        return None


# ============================================================
# ROLES ELECTORALES
# ============================================================

class ElectoralRole(enum.Enum):
    """Roles para el sistema electoral."""
    VIEWER = "VIEWER"          # Solo puede ver resultados
    OPERATOR = "OPERATOR"      # Puede procesar E-14
    VALIDATOR = "VALIDATOR"    # Puede validar y corregir
    AUDITOR = "AUDITOR"        # Puede ver auditoría
    ADMIN = "ADMIN"            # Acceso total


# Permisos por rol
ROLE_PERMISSIONS = {
    ElectoralRole.VIEWER: ['view_results', 'view_stats'],
    ElectoralRole.OPERATOR: ['view_results', 'view_stats', 'process_e14', 'upload_e14'],
    ElectoralRole.VALIDATOR: ['view_results', 'view_stats', 'process_e14', 'upload_e14',
                              'validate_e14', 'correct_e14'],
    ElectoralRole.AUDITOR: ['view_results', 'view_stats', 'view_audit', 'export_data'],
    ElectoralRole.ADMIN: ['*'],  # Todos los permisos
}


# ============================================================
# COST TRACKER (In-Memory para esta versión)
# ============================================================

class CostTracker:
    """
    Tracker de costos de API por usuario.
    Persistencia en memoria para esta versión.
    """

    # Costo estimado por operación (desde Config)
    COST_PER_E14_PROCESS = Config.E14_COST_PER_PROCESS  # USD

    # Límites (desde Config)
    DEFAULT_DAILY_LIMIT = Config.E14_DAILY_COST_LIMIT   # USD por usuario/día
    DEFAULT_HOURLY_LIMIT = Config.E14_HOURLY_COST_LIMIT  # USD por usuario/hora

    def __init__(self):
        self._usage: Dict[str, List[Dict]] = {}  # user_id -> [{timestamp, cost}]
        self._lock = threading.Lock()

    def record_usage(self, user_id: str, cost: float, operation: str = "e14_process"):
        """Registra uso de API."""
        with self._lock:
            if user_id not in self._usage:
                self._usage[user_id] = []

            self._usage[user_id].append({
                'timestamp': datetime.utcnow(),
                'cost': cost,
                'operation': operation
            })

            # Limpiar registros viejos (>24h)
            cutoff = datetime.utcnow() - timedelta(hours=24)
            self._usage[user_id] = [
                u for u in self._usage[user_id]
                if u['timestamp'] > cutoff
            ]

    def get_usage(self, user_id: str, hours: int = 24) -> Dict:
        """Obtiene uso de un usuario."""
        with self._lock:
            if user_id not in self._usage:
                return {'cost': 0.0, 'operations': 0}

            cutoff = datetime.utcnow() - timedelta(hours=hours)
            recent = [u for u in self._usage[user_id] if u['timestamp'] > cutoff]

            return {
                'cost': sum(u['cost'] for u in recent),
                'operations': len(recent)
            }

    def check_limit(
        self,
        user_id: str,
        daily_limit: float = None,
        hourly_limit: float = None
    ) -> tuple[bool, str]:
        """
        Verifica si el usuario puede realizar otra operación.

        Returns:
            (allowed, message)
        """
        daily_limit = daily_limit or self.DEFAULT_DAILY_LIMIT
        hourly_limit = hourly_limit or self.DEFAULT_HOURLY_LIMIT

        # Verificar límite por hora
        hourly_usage = self.get_usage(user_id, hours=1)
        if hourly_usage['cost'] >= hourly_limit:
            return False, f"Límite por hora excedido: ${hourly_usage['cost']:.2f}/${hourly_limit:.2f}"

        # Verificar límite diario
        daily_usage = self.get_usage(user_id, hours=24)
        if daily_usage['cost'] >= daily_limit:
            return False, f"Límite diario excedido: ${daily_usage['cost']:.2f}/${daily_limit:.2f}"

        return True, "OK"

    def get_all_stats(self) -> Dict:
        """Obtiene estadísticas globales."""
        with self._lock:
            total_cost = 0.0
            total_ops = 0
            users_active = len(self._usage)

            for user_id, usage_list in self._usage.items():
                total_cost += sum(u['cost'] for u in usage_list)
                total_ops += len(usage_list)

            return {
                'total_cost_24h': total_cost,
                'total_operations_24h': total_ops,
                'active_users': users_active
            }


# Singleton del cost tracker
_cost_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Obtiene el singleton del cost tracker."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker


# ============================================================
# DECORADORES DE SEGURIDAD
# ============================================================

def electoral_auth_required(f):
    """
    Decorator que requiere autenticación para endpoints electorales.
    Almacena user_id en g.electoral_user_id
    Trackea métricas de autenticación (QAS Sec1)
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        metrics = _get_security_metrics()
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            g.electoral_user_id = user_id

            # Métrica de auth exitoso
            if metrics:
                metrics.track_auth_attempt("success", "jwt")

            return f(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Auth failed for electoral endpoint: {e}")

            # Métrica de auth fallido
            if metrics:
                metrics.track_auth_attempt("failure", "jwt")

            return jsonify({
                'success': False,
                'error': 'Autenticación requerida',
                'code': 'AUTH_REQUIRED'
            }), 401

    return decorated


def require_electoral_role(allowed_roles: List[ElectoralRole]):
    """
    Decorator que verifica rol electoral del usuario.
    Trackea métricas de autorización (QAS Sec1)

    Usage:
        @require_electoral_role([ElectoralRole.OPERATOR, ElectoralRole.ADMIN])
        def process_e14():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            metrics = _get_security_metrics()
            resource = request.endpoint or "unknown"
            action = request.method

            # Primero verificar autenticación
            try:
                verify_jwt_in_request()
                user_id = get_jwt_identity()
                g.electoral_user_id = user_id
            except Exception:
                if metrics:
                    metrics.track_auth_attempt("failure", "jwt")
                return jsonify({
                    'success': False,
                    'error': 'Autenticación requerida',
                    'code': 'AUTH_REQUIRED'
                }), 401

            # TODO: Obtener rol del usuario desde BD
            # Por ahora, asumimos OPERATOR para usuarios autenticados
            user_role = ElectoralRole.OPERATOR

            # Verificar si el rol está permitido
            if user_role not in allowed_roles and ElectoralRole.ADMIN not in allowed_roles:
                if user_role != ElectoralRole.ADMIN:
                    logger.warning(f"Authorization denied for user {user_id}: requires {allowed_roles}, has {user_role}")

                    # Métrica de autorización denegada
                    if metrics:
                        metrics.track_authz_check(resource, action, allowed=False)

                    return jsonify({
                        'success': False,
                        'error': f'Rol insuficiente. Se requiere: {[r.value for r in allowed_roles]}',
                        'code': 'INSUFFICIENT_ROLE'
                    }), 403

            # Métrica de autorización exitosa
            if metrics:
                metrics.track_authz_check(resource, action, allowed=True)

            g.electoral_role = user_role
            return f(*args, **kwargs)

        return decorated
    return decorator


def cost_limit_check(cost: float = None):
    """
    Decorator que verifica límites de costo antes de operaciones costosas.
    Trackea métricas de rate limiting (QAS Sec1)

    Args:
        cost: Costo de la operación (default: COST_PER_E14_PROCESS)
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            metrics = _get_security_metrics()
            operation_cost = cost or CostTracker.COST_PER_E14_PROCESS
            endpoint = request.endpoint or "unknown"

            # Obtener user_id (debe estar autenticado)
            user_id = getattr(g, 'electoral_user_id', None)
            if not user_id:
                try:
                    verify_jwt_in_request()
                    user_id = get_jwt_identity()
                except Exception:
                    return jsonify({
                        'success': False,
                        'error': 'Autenticación requerida para operaciones con costo',
                        'code': 'AUTH_REQUIRED'
                    }), 401

            # Verificar límites
            tracker = get_cost_tracker()
            allowed, message = tracker.check_limit(user_id)

            if not allowed:
                logger.warning(f"Cost limit exceeded for user {user_id}: {message}")

                # Métrica de rate limit hit
                if metrics:
                    metrics.track_rate_limit_hit(endpoint, user_id)

                return jsonify({
                    'success': False,
                    'error': message,
                    'code': 'COST_LIMIT_EXCEEDED',
                    'usage': tracker.get_usage(user_id, hours=24)
                }), 429  # Too Many Requests

            # Ejecutar función
            result = f(*args, **kwargs)

            # Registrar costo si fue exitoso
            # (verificamos el status code del response)
            if hasattr(result, '__iter__') and len(result) == 2:
                response, status_code = result
                if status_code == 200:
                    tracker.record_usage(user_id, operation_cost)
            elif hasattr(result, 'status_code') and result.status_code == 200:
                tracker.record_usage(user_id, operation_cost)
            else:
                # Respuesta simple exitosa
                tracker.record_usage(user_id, operation_cost)

            return result

        return decorated
    return decorator


def log_electoral_action(action: str):
    """
    Decorator para logging de acciones electorales en audit_log.
    Trackea métricas de auditoría (QAS I2)

    Args:
        action: Nombre de la acción (CREATE, PROCESS, VALIDATE, etc.)
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            metrics = _get_security_metrics()
            start_time = time.time()
            user_id = getattr(g, 'electoral_user_id', 'anonymous')
            user_role = getattr(g, 'electoral_role', ElectoralRole.OPERATOR)
            role_value = user_role.value if hasattr(user_role, 'value') else str(user_role)

            # Log inicio
            logger.info(f"Electoral action START: {action} by user {user_id}")

            try:
                result = f(*args, **kwargs)

                # Log éxito
                elapsed_ms = int((time.time() - start_time) * 1000)
                logger.info(f"Electoral action SUCCESS: {action} by user {user_id} ({elapsed_ms}ms)")

                # Métrica de evento de auditoría
                if metrics:
                    metrics.track_audit_event(action, "e14", role_value)

                # TODO: Insertar en audit_log de BD
                # audit_entry = AuditLog(
                #     actor_user_id=user_id,
                #     action=action,
                #     entity_type='e14',
                #     ...
                # )

                return result

            except Exception as e:
                elapsed_ms = int((time.time() - start_time) * 1000)
                logger.error(f"Electoral action FAILED: {action} by user {user_id} ({elapsed_ms}ms): {e}")

                # Métrica de acción fallida
                if metrics:
                    metrics.track_audit_event(f"{action}_FAILED", "e14", role_value)

                raise

        return decorated
    return decorator


# ============================================================
# HELPERS
# ============================================================

def get_client_ip() -> str:
    """Obtiene IP del cliente (considerando proxies)."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    return request.remote_addr or 'unknown'


def get_request_metadata() -> Dict:
    """Obtiene metadata de la request actual."""
    return {
        'ip': get_client_ip(),
        'user_agent': request.headers.get('User-Agent', 'unknown'),
        'timestamp': datetime.utcnow().isoformat(),
        'endpoint': request.endpoint,
        'method': request.method
    }
