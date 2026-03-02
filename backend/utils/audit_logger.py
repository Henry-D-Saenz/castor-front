"""
Audit Logger for CASTOR Elecciones.

Provides compliance-ready logging for:
- User actions (analysis requests, data access)
- System events (authentication, errors)
- API usage (rate limits, quotas)

For legal compliance (Ley 1581 de Habeas Data - Colombia).
"""
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps
from flask import request, g
import hashlib

# Configure audit logger
audit_logger = logging.getLogger("castor.audit")
audit_logger.setLevel(logging.INFO)

# Create handler if not exists
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - AUDIT - %(message)s'
    ))
    audit_logger.addHandler(handler)


class AuditEventType:
    """Audit event types for categorization."""
    # Authentication events
    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_FAILED = "auth.failed"
    AUTH_TOKEN_REFRESH = "auth.token_refresh"

    # Data access events
    DATA_READ = "data.read"
    DATA_WRITE = "data.write"
    DATA_DELETE = "data.delete"
    DATA_EXPORT = "data.export"

    # Analysis events
    ANALYSIS_MEDIA = "analysis.media"
    ANALYSIS_CAMPAIGN = "analysis.campaign"
    ANALYSIS_FORECAST = "analysis.forecast"
    ANALYSIS_GAME_THEORY = "analysis.game_theory"

    # API events
    API_CALL = "api.call"
    API_RATE_LIMITED = "api.rate_limited"
    API_ERROR = "api.error"

    # Admin events
    ADMIN_CONFIG_CHANGE = "admin.config_change"
    ADMIN_USER_CREATED = "admin.user_created"

    # Security events
    SECURITY_SUSPICIOUS = "security.suspicious"
    SECURITY_BLOCKED = "security.blocked"


def _get_client_ip() -> str:
    """Get client IP address, handling proxies."""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    return request.remote_addr or 'unknown'


def _hash_pii(value: str) -> str:
    """Hash PII data for privacy compliance."""
    if not value:
        return 'none'
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _sanitize_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove or hash sensitive data before logging."""
    sensitive_fields = ['password', 'token', 'api_key', 'secret', 'bearer']
    pii_fields = ['email', 'phone', 'name', 'first_name', 'last_name']

    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(sf in key_lower for sf in sensitive_fields):
            sanitized[key] = '[REDACTED]'
        elif any(pf in key_lower for pf in pii_fields):
            sanitized[key] = _hash_pii(str(value)) if value else None
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_data(value)
        else:
            sanitized[key] = value
    return sanitized


def log_audit_event(
    event_type: str,
    action: str,
    resource: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    user_id: Optional[str] = None,
    success: bool = True,
    error_message: Optional[str] = None
):
    """
    Log an audit event.

    Args:
        event_type: Type of event (use AuditEventType constants)
        action: Description of the action taken
        resource: Resource being accessed (e.g., endpoint, data type)
        details: Additional details (will be sanitized)
        user_id: User identifier (will be hashed)
        success: Whether the action was successful
        error_message: Error message if failed
    """
    try:
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "action": action,
            "success": success,
            "client": {
                "ip": _get_client_ip(),
                "user_agent": request.headers.get('User-Agent', 'unknown')[:100],
                "user_id_hash": _hash_pii(user_id) if user_id else None
            },
            "request": {
                "method": request.method,
                "path": request.path,
                "endpoint": request.endpoint
            }
        }

        if resource:
            event["resource"] = resource

        if details:
            event["details"] = _sanitize_data(details)

        if error_message:
            event["error"] = error_message[:500]  # Limit error message length

        # Log as JSON for easy parsing
        audit_logger.info(json.dumps(event, ensure_ascii=False))

    except Exception as e:
        # Don't let audit logging break the application
        logging.error(f"Audit logging failed: {e}")


def audit_endpoint(event_type: str, resource: str = None):
    """
    Decorator to automatically audit API endpoints.

    Usage:
        @app.route('/api/analysis')
        @audit_endpoint(AuditEventType.ANALYSIS_MEDIA, "media_analysis")
        def analyze():
            ...
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            start_time = datetime.utcnow()
            success = True
            error_msg = None

            try:
                result = f(*args, **kwargs)
                # Check if result is a tuple (response, status_code)
                if isinstance(result, tuple) and len(result) >= 2:
                    if result[1] >= 400:
                        success = False
                return result
            except Exception as e:
                success = False
                error_msg = str(e)
                raise
            finally:
                # Calculate duration
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

                # Get user_id from Flask g object if available
                user_id = getattr(g, 'user_id', None) or getattr(g, 'current_user', None)

                log_audit_event(
                    event_type=event_type,
                    action=f"Endpoint: {f.__name__}",
                    resource=resource or request.endpoint,
                    details={
                        "duration_ms": round(duration_ms, 2),
                        "query_params": dict(request.args),
                        "content_length": request.content_length
                    },
                    user_id=str(user_id) if user_id else None,
                    success=success,
                    error_message=error_msg
                )
        return wrapper
    return decorator


# Convenience functions for common audit events
def audit_analysis_request(
    analysis_type: str,
    location: str,
    topic: str = None,
    candidate: str = None,
    success: bool = True,
    tweets_analyzed: int = 0
):
    """Log an analysis request event."""
    event_type = {
        "media": AuditEventType.ANALYSIS_MEDIA,
        "campaign": AuditEventType.ANALYSIS_CAMPAIGN,
        "forecast": AuditEventType.ANALYSIS_FORECAST,
    }.get(analysis_type, AuditEventType.API_CALL)

    log_audit_event(
        event_type=event_type,
        action=f"Analysis request: {analysis_type}",
        resource=f"/api/{analysis_type}/analyze",
        details={
            "location": location,
            "topic": topic,
            "candidate": _hash_pii(candidate) if candidate else None,
            "tweets_analyzed": tweets_analyzed
        },
        success=success
    )


def audit_authentication(
    action: str,
    user_email: str,
    success: bool,
    failure_reason: str = None
):
    """Log an authentication event."""
    event_type = AuditEventType.AUTH_LOGIN if success else AuditEventType.AUTH_FAILED

    log_audit_event(
        event_type=event_type,
        action=action,
        resource="authentication",
        details={
            "failure_reason": failure_reason
        },
        user_id=user_email,
        success=success,
        error_message=failure_reason
    )


def audit_rate_limit(endpoint: str, limit: str, user_id: str = None):
    """Log a rate limit event."""
    log_audit_event(
        event_type=AuditEventType.API_RATE_LIMITED,
        action="Rate limit exceeded",
        resource=endpoint,
        details={"limit": limit},
        user_id=user_id,
        success=False,
        error_message=f"Rate limit exceeded: {limit}"
    )


def audit_security_event(
    action: str,
    details: Dict[str, Any],
    blocked: bool = False
):
    """Log a security event."""
    event_type = AuditEventType.SECURITY_BLOCKED if blocked else AuditEventType.SECURITY_SUSPICIOUS

    log_audit_event(
        event_type=event_type,
        action=action,
        resource="security",
        details=details,
        success=not blocked,
        error_message="Request blocked" if blocked else None
    )
