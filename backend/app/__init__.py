"""
Flask application factory for CASTOR ELECCIONES.
"""
from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
import logging
import sys

try:
    from flask_compress import Compress
    compress = Compress()
    COMPRESS_AVAILABLE = True
except ImportError:
    compress = None
    COMPRESS_AVAILABLE = False

from config import Config, config as config_map
from utils.rate_limiter import init_rate_limiter
from utils.cache import init_cache
# Service imports moved inside create_app to avoid circular imports

# Initialize extensions
cors = CORS()
jwt = JWTManager()


def create_app(config_name: str = 'default') -> Flask:
    """
    Application factory pattern.
    
    Args:
        config_name: Configuration name (development, production, testing)
        
    Returns:
        Flask application instance
    """
    # Determine template and static folders
    # Check if templates exist in parent directory (root of project)
    import os
    # __file__ is backend/app/__init__.py
    # os.path.dirname(__file__) = backend/app/
    # os.path.dirname(os.path.dirname(__file__)) = backend/
    # os.path.dirname(os.path.dirname(os.path.dirname(__file__))) = project root
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
    project_root = os.path.dirname(backend_dir)  # project root
    parent_templates = os.path.join(project_root, 'templates')
    parent_static = os.path.join(project_root, 'static')
    
    template_folder = parent_templates if os.path.exists(parent_templates) else 'templates'
    static_folder = parent_static if os.path.exists(parent_static) else 'static'
    
    app = Flask(
        __name__,
        template_folder=template_folder,
        static_folder=static_folder
    )
    
    # Load configuration based on requested environment
    config_class = config_map.get(config_name, Config)
    try:
        config_class.validate()
    except ValueError as exc:
        # Allow dev/default to boot with warnings; enforce in other environments
        is_dev_env = getattr(config_class, "DEBUG", False) or config_name in ('development', 'default')
        if is_dev_env:
            logging.warning("Configuration validation warning: %s", exc)
        else:
            raise
    app.config.from_object(config_class)
    
    # Initialize extensions
    cors.init_app(app, resources={
        r"/api/*": {
            "origins": Config.CORS_ORIGINS,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    jwt.init_app(app)

    # HTTPS enforcement in production
    if not app.debug and os.environ.get('FORCE_HTTPS', 'true').lower() == 'true':
        from flask import request, redirect

        @app.before_request
        def enforce_https():
            """Redirect HTTP to HTTPS in production."""
            # Check X-Forwarded-Proto header (set by reverse proxy/load balancer)
            if request.headers.get('X-Forwarded-Proto', 'http') != 'https':
                if request.url.startswith('http://'):
                    url = request.url.replace('http://', 'https://', 1)
                    return redirect(url, code=301)

        @app.after_request
        def add_security_headers(response):
            """Add security headers to all responses."""
            response.headers['X-Content-Type-Options'] = 'nosniff'
            # Allow same-origin iframes (used by the in-app E-14 PDF viewer modal).
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['X-XSS-Protection'] = '1; mode=block'
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            # HSTS - only enable in production with valid SSL
            if os.environ.get('ENABLE_HSTS', 'false').lower() == 'true':
                response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            return response
    
    # Initialize rate limiting
    init_rate_limiter(app)

    # Initialize caching
    init_cache()

    # Initialize response compression (if available)
    if COMPRESS_AVAILABLE and compress:
        app.config['COMPRESS_ALGORITHM'] = 'gzip'
        app.config['COMPRESS_LEVEL'] = 6
        app.config['COMPRESS_MIN_SIZE'] = 500
        compress.init_app(app)

    # Initialize background jobs only when full backend is enabled
    front_only_mode = bool(getattr(Config, "FRONT_ONLY_MODE", False))
    if not front_only_mode:
        from services.background_jobs import init_background_jobs
        init_background_jobs()

    # Configure logging with multiple handlers
    log_level = getattr(logging, Config.LOG_LEVEL, logging.INFO)
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Create handlers list
    handlers = [logging.StreamHandler(sys.stdout)]
    if Config.LOG_FILE:
        handlers.append(logging.FileHandler(Config.LOG_FILE))

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers
    )
    
    # Initialize shared services (best-effort, non-fatal) only in full mode
    if not front_only_mode:
        try:
            from services.database_service import DatabaseService
            db_service = DatabaseService()
            app.extensions["database_service"] = db_service

            # Initialize RAG service with database connection
            try:
                from services.rag_service import init_rag_service
                rag_service = init_rag_service(db_service=db_service)
                app.extensions["rag_service"] = rag_service
                logging.info(f"RAG service initialized with {rag_service.vector_store.count()} documents")
            except Exception as rag_exc:
                logging.warning(f"RAG service not initialized: {rag_exc}")
                app.extensions["rag_service"] = None

        except Exception as exc:
            logging.warning(f"Core services not fully initialized: {exc}")
            app.extensions["rag_service"] = None
    else:
        app.extensions["rag_service"] = None
        logging.info("FRONT_ONLY_MODE enabled: skipping DB/RAG/background workers and non-dashboard blueprints")

    if front_only_mode:
        # Minimal routes for dashboard rendering only.
        from flask import request, session, redirect, url_for, jsonify
        from services.electoral_access import _SESSION_KEY
        from app.routes.health import health_bp
        from app.routes.web import web_bp
        from app.routes.electoral_auth import electoral_auth_bp
        from app.routes.incidents import incidents_bp
        from app.routes.geography import geography_bp
        from app.routes.e14_data import e14_data_bp, start_registry_bootstrap_async
        from app.routes.campaign_team import campaign_team_bp
        app.register_blueprint(electoral_auth_bp)  # /electoral/login, /electoral/logout
        app.register_blueprint(web_bp)  # No prefix for web routes
        app.register_blueprint(health_bp, url_prefix='/api')
        app.register_blueprint(incidents_bp, url_prefix='/api/incidents')
        app.register_blueprint(geography_bp, url_prefix='/api/geography')
        app.register_blueprint(e14_data_bp)  # E-14 data APIs used by front
        app.register_blueprint(campaign_team_bp, url_prefix='/api/campaign-team')
        start_registry_bootstrap_async()

        @app.get("/healthz")
        def healthz_front_only():
            """Unauthenticated warmup/readiness endpoint for App Service probes."""
            return jsonify({"ok": True}), 200

        @app.before_request
        def require_login_front_only():
            """Deny access to all routes unless user is logged in."""
            path = request.path or "/"
            allowed = (
                path.startswith('/static/')
                or path in ('/electoral/login', '/electoral/logout', '/favicon.ico')
                or path == '/healthz'
                or path == '/api/e14-data/webhook/completed'
            )
            if allowed:
                return None
            if _SESSION_KEY in session:
                return None
            if path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('electoral_auth.login'))
    else:
        # Full backend routes.
        from app.routes.chat import chat_bp
        from app.routes.health import health_bp
        from app.routes.auth import auth_bp
        from app.routes.web import web_bp
        from app.routes.review import review_bp
        from app.routes.incidents import incidents_bp
        from app.routes.geography import geography_bp
        from app.routes.scraper import scraper_bp
        from app.routes.e14_data import e14_data_bp, start_registry_bootstrap_async
        from app.routes.agent import agent_bp
        from app.routes.electoral_auth import electoral_auth_bp
        from app.routes.campaign_team import campaign_team_bp
        app.register_blueprint(electoral_auth_bp)  # Electoral access login (no prefix)
        app.register_blueprint(web_bp)  # No prefix for web routes
        app.register_blueprint(chat_bp, url_prefix='/api')
        app.register_blueprint(health_bp, url_prefix='/api')
        app.register_blueprint(auth_bp, url_prefix='/api')
        app.register_blueprint(review_bp, url_prefix='/api/electoral/review')
        app.register_blueprint(incidents_bp, url_prefix='/api/incidents')
        app.register_blueprint(geography_bp, url_prefix='/api/geography')
        app.register_blueprint(scraper_bp)  # Already has /api/scraper prefix
        app.register_blueprint(e14_data_bp)  # E-14 scraper data API
        app.register_blueprint(agent_bp, url_prefix='/api/agent')  # Electoral Intelligence Agent
        app.register_blueprint(campaign_team_bp, url_prefix='/api/campaign-team')  # War Room Dashboard
        start_registry_bootstrap_async()

    # Register error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Endpoint not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'error': 'Internal server error'}, 500
    
    @app.errorhandler(400)
    def bad_request(error):
        return {'error': 'Bad request'}, 400
    
    return app
