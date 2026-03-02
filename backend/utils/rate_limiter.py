"""
Rate limiting utilities using Flask-Limiter.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import get_jwt_identity
from config import Config


def get_rate_limit_key():
    """
    Get rate limit key based on user authentication.
    Uses user ID if authenticated, otherwise IP address.
    """
    try:
        user_id = get_jwt_identity()
        if user_id:
            return f"user:{user_id}"
    except RuntimeError:
        # No JWT token in request, use IP address
        pass
    return get_remote_address()


# Initialize limiter (will be initialized in app factory)
limiter = Limiter(
    key_func=get_rate_limit_key,
    default_limits=[f"{Config.RATE_LIMIT_PER_MINUTE} per minute"],
    storage_uri=Config.RATE_LIMIT_STORAGE_URI,
    strategy="fixed-window"
)


def init_rate_limiter(app):
    """
    Initialize rate limiter with Flask app.

    Args:
        app: Flask application instance
    """
    limiter.init_app(app)

    # Apply rate limits to specific endpoints
    # These can be overridden per route
    app.config['RATELIMIT_ENABLED'] = True

    # Exempt internal dashboard routes from strict rate limiting
    # Campaign team dashboard makes many parallel calls on load
    app.config['RATELIMIT_HEADERS_ENABLED'] = True

    return limiter


def exempt_blueprint(blueprint):
    """
    Exempt an entire blueprint from rate limiting.
    Use for internal dashboard routes that make many parallel calls.

    Args:
        blueprint: Flask blueprint to exempt
    """
    @blueprint.before_request
    def exempt_from_rate_limit():
        from flask import g
        g._rate_limit_exempt = True
