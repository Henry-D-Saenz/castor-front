"""
Configuration module for CASTOR ELECCIONES backend.
Handles environment variables and application settings.
"""
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


class Config:
    """Base configuration class."""

    # Flask - SECURITY: SECRET_KEY must be set in production
    SECRET_KEY: str = os.getenv('SECRET_KEY', '')
    DEBUG: bool = os.getenv('DEBUG', 'False').lower() == 'true'
    TESTING: bool = False

    # Session
    from datetime import timedelta as _td
    PERMANENT_SESSION_LIFETIME: _td = _td(hours=int(os.getenv('SESSION_LIFETIME_HOURS', '8')))

    # Security validation
    _SECRET_KEY_MIN_LENGTH: int = 32
    
    # Server
    HOST: str = os.getenv('HOST', '0.0.0.0')
    PORT: int = int(os.getenv('PORT', '5001'))

    # Front-only profile for dashboard rendering.
    # When enabled, the app boots only the minimal API/routes needed by the UI.
    FRONT_ONLY_MODE: bool = os.getenv('FRONT_ONLY_MODE', 'true').lower() == 'true'
    # Front-only login users list (JSON string):
    # [{"cedula":"1234567890","code":"ABCD-EFGH-IJKL-MNOP","name":"Nombre"}]
    ELECTORAL_ACCESS_USERS: str = os.getenv('ELECTORAL_ACCESS_USERS', '[]')
    
    # CORS
    CORS_ORIGINS: list = os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',')
    
    # JWT
    JWT_SECRET_KEY: str = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES: int = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', '3600'))  # 1 hour
    
    # Twitter API (Tweepy)
    TWITTER_BEARER_TOKEN: Optional[str] = os.getenv('TWITTER_BEARER_TOKEN')
    TWITTER_API_KEY: Optional[str] = os.getenv('TWITTER_API_KEY')
    TWITTER_API_SECRET: Optional[str] = os.getenv('TWITTER_API_SECRET')
    TWITTER_ACCESS_TOKEN: Optional[str] = os.getenv('TWITTER_ACCESS_TOKEN')
    TWITTER_ACCESS_TOKEN_SECRET: Optional[str] = os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
    TWITTER_TIMEOUT_SECONDS: int = int(os.getenv('TWITTER_TIMEOUT_SECONDS', '15'))

    # Twitter Free Tier Limits (100 posts/month)
    TWITTER_MIN_RESULTS: int = int(os.getenv('TWITTER_MIN_RESULTS', '10'))
    TWITTER_MAX_RESULTS_PER_REQUEST: int = int(os.getenv('TWITTER_MAX_RESULTS_PER_REQUEST', '15'))
    TWITTER_MONTHLY_LIMIT: int = int(os.getenv('TWITTER_MONTHLY_LIMIT', '100'))
    TWITTER_DAILY_REQUEST_LIMIT: int = int(os.getenv('TWITTER_DAILY_REQUEST_LIMIT', '3'))
    
    # LLM Provider Selection (openai, claude, local)
    LLM_PROVIDER: str = os.getenv('LLM_PROVIDER', 'openai')

    # OpenAI
    OPENAI_API_KEY: Optional[str] = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL: str = os.getenv('OPENAI_MODEL', 'gpt-4o')
    OPENAI_EMBEDDING_MODEL: str = os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small')
    OPENAI_TIMEOUT_SECONDS: int = int(os.getenv('OPENAI_TIMEOUT_SECONDS', '60'))  # Increased for long content generation

    # Anthropic Claude
    ANTHROPIC_API_KEY: Optional[str] = os.getenv('ANTHROPIC_API_KEY')
    CLAUDE_MODEL: str = os.getenv('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')
    CLAUDE_VISION_MODEL: str = os.getenv('CLAUDE_VISION_MODEL', 'claude-sonnet-4-20250514')

    # E-14 Data Directories (centralized)
    E14_DATA_DIR: str = os.getenv(
        'E14_DATA_DIR',
        str(Path(__file__).parent.parent / 'data' / 'e14')
    )
    E14_RAW_DIR: str = os.path.join(E14_DATA_DIR, 'raw')
    E14_PROCESSED_DIR: str = os.path.join(E14_DATA_DIR, 'processed')
    E14_FAILED_DIR: str = os.path.join(E14_DATA_DIR, 'failed')
    E14_TRAINING_DIR: str = os.path.join(E14_DATA_DIR, 'training')
    E14_AZURE_RESULTS_DIR: str = os.path.join(E14_PROCESSED_DIR, 'azure_results')
    E14_JSON_STORE_TTL: int = int(os.getenv('E14_JSON_STORE_TTL', '300'))
    # On startup, replay document_ids.log and recover OCR results into in-memory store.
    E14_BOOTSTRAP_FROM_REGISTRY: bool = os.getenv(
        'E14_BOOTSTRAP_FROM_REGISTRY', 'true'
    ).lower() == 'true'
    E14_BOOTSTRAP_BATCH_SIZE: int = int(os.getenv('E14_BOOTSTRAP_BATCH_SIZE', '50'))

    # Electoral SQLite store (incidents + agent state)
    CASTOR_DB_PATH: str = os.getenv(
        'CASTOR_DB_PATH',
        str(Path(__file__).resolve().parent / 'data' / 'castor.db')
    )

    # Electoral Control / E-14 OCR
    E14_OCR_MAX_PAGES: int = int(os.getenv('E14_OCR_MAX_PAGES', '20'))
    E14_OCR_TIMEOUT: int = int(os.getenv('E14_OCR_TIMEOUT', '300'))
    E14_OCR_DPI: int = int(os.getenv('E14_OCR_DPI', '150'))

    # Electoral API Security Limits
    E14_COST_PER_PROCESS: float = float(os.getenv('E14_COST_PER_PROCESS', '0.10'))
    E14_HOURLY_COST_LIMIT: float = float(os.getenv('E14_HOURLY_COST_LIMIT', '10.00'))
    E14_DAILY_COST_LIMIT: float = float(os.getenv('E14_DAILY_COST_LIMIT', '10.00'))
    E14_MAX_FILE_SIZE_MB: int = int(os.getenv('E14_MAX_FILE_SIZE_MB', '10'))
    E14_MAX_PAGES: int = int(os.getenv('E14_MAX_PAGES', '20'))

    # Azure OCR Service
    AZURE_OCR_URL: str = os.getenv(
        "AZURE_OCR_URL",
        "https://castor-ocr-hpcxdsbmeqgvdebd.centralus-01.azurewebsites.net"
    )
    AZURE_OCR_API_KEY: str = os.getenv("AZURE_OCR_API_KEY", "")
    AZURE_STORAGE_CONNECTION_STRING: str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()
    AZURE_STORAGE_CONTAINER_NAME: str = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "").strip()
    # Optional upstream "results" API (app #1) used as primary source for OCR output.
    RESULTS_API_BASE_URL: str = os.getenv("RESULTS_API_BASE_URL", "").strip()
    RESULTS_API_KEY: str = os.getenv("RESULTS_API_KEY", "").strip()
    RESULTS_API_TIMEOUT_SECONDS: int = int(os.getenv("RESULTS_API_TIMEOUT_SECONDS", "15"))
    RESULTS_API_RESULTS_PATH_TEMPLATE: str = os.getenv(
        "RESULTS_API_RESULTS_PATH_TEMPLATE",
        "/api/v1/documents/{document_id}/results",
    )
    RESULTS_API_METADATA_PATH_TEMPLATE: str = os.getenv(
        "RESULTS_API_METADATA_PATH_TEMPLATE",
        "/api/v1/documents/{document_id}",
    )
    # Shared token to authorize inbound completion webhooks from upstream apps.
    OCR_WEBHOOK_TOKEN: str = os.getenv("OCR_WEBHOOK_TOKEN", "")
    # SQL queue/cache mode for large-scale document volumes.
    E14_SQL_QUEUE_ENABLED: bool = os.getenv("E14_SQL_QUEUE_ENABLED", "false").lower() == "true"
    E14_SQL_CONNECTION_STRING: str = os.getenv("E14_SQL_CONNECTION_STRING", "").strip()
    E14_SQL_WORKER_BATCH_SIZE: int = int(os.getenv("E14_SQL_WORKER_BATCH_SIZE", "200"))
    E14_SQL_WORKER_POLL_SECONDS: int = int(os.getenv("E14_SQL_WORKER_POLL_SECONDS", "5"))
    E14_FLAT_DIR: str = os.getenv(
        "E14_FLAT_DIR",
        str(Path(__file__).parent.parent / "data" / "e14" / "raw" / "flat")
    )

    # PMSN rules configuration (allow overriding the municipios pareto list)
    PMSN_PARETO_FILE: str = os.getenv(
        'PMSN_PARETO_FILE',
        str(Path(__file__).parent / 'MUNICIPIOSRIESGOS.JSON')
    )

    # Local LLM (Ollama)
    LOCAL_LLM_URL: str = os.getenv('LOCAL_LLM_URL', os.getenv('OLLAMA_URL', 'http://localhost:11434'))
    LOCAL_LLM_MODEL: str = os.getenv('LOCAL_LLM_MODEL', os.getenv('LLM_MODEL', 'llama3'))
    
    # Database — normalize relative sqlite:///./path to absolute so codes
    # survive server restarts regardless of working directory.
    _raw_db_url: str = os.getenv(
        'DATABASE_URL',
        f"sqlite:///{str(Path(__file__).resolve().parent / 'data' / 'castor.db')}"
    )
    if _raw_db_url.startswith('sqlite:///') and not _raw_db_url.startswith('sqlite:////'):
        _rel = _raw_db_url[len('sqlite:///'):]
        _abs = str(Path(__file__).resolve().parent / _rel)
        DATABASE_URL: Optional[str] = f"sqlite:///{_abs}"
    else:
        DATABASE_URL: Optional[str] = _raw_db_url  # type: ignore[no-redef]
    SQLALCHEMY_DATABASE_URI: Optional[str] = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SQLALCHEMY_ECHO: bool = DEBUG

    # Database Pool Configuration
    DB_POOL_SIZE: int = int(os.getenv('DB_POOL_SIZE', '10'))
    DB_MAX_OVERFLOW: int = int(os.getenv('DB_MAX_OVERFLOW', '20'))
    DB_POOL_TIMEOUT: int = int(os.getenv('DB_POOL_TIMEOUT', '30'))
    
    # BETO Model
    BETO_MODEL_PATH: str = os.getenv('BETO_MODEL_PATH', 'dccuchile/bert-base-spanish-wwm-uncased')
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv('RATE_LIMIT_PER_MINUTE', '120'))  # 2 per second - dashboard makes parallel calls
    RATE_LIMIT_STORAGE_URI: str = os.getenv('RATE_LIMIT_STORAGE_URI', 'memory://')
    
    # Caching
    CACHE_MAX_SIZE: int = int(os.getenv('CACHE_MAX_SIZE', '64'))
    SENTIMENT_CACHE_TTL: int = int(os.getenv('SENTIMENT_CACHE_TTL', '900'))
    OPENAI_CACHE_TTL: int = int(os.getenv('OPENAI_CACHE_TTL', '1800'))
    TRENDING_CACHE_TTL: int = int(os.getenv('TRENDING_CACHE_TTL', '600'))
    TRENDING_CACHE_STALE_TTL: int = int(os.getenv('TRENDING_CACHE_STALE_TTL', '300'))
    
    # Caching (memory-only backend in this profile)
    CACHE_TTL_TWITTER: int = int(os.getenv('CACHE_TTL_TWITTER', '86400'))  # 24 hours (agresivo para conservar rate limit)
    CACHE_TTL_SENTIMENT: int = int(os.getenv('CACHE_TTL_SENTIMENT', '86400'))  # 24 hours
    CACHE_TTL_OPENAI: int = int(os.getenv('CACHE_TTL_OPENAI', '43200'))  # 12 hours
    CACHE_TTL_TRENDING: int = int(os.getenv('CACHE_TTL_TRENDING', '21600'))  # 6 hours
    
    # Twitter Basic Plan Limits ($200/month - 15,000 posts/month)
    TWITTER_MAX_TWEETS_PER_REQUEST: int = int(os.getenv('TWITTER_MAX_TWEETS_PER_REQUEST', '500'))  # Máximo por request (límite diario)
    TWITTER_DAILY_TWEET_LIMIT: int = int(os.getenv('TWITTER_DAILY_TWEET_LIMIT', '500'))  # ~15000/30 días = 500 por día
    TWITTER_MONTHLY_LIMIT: int = int(os.getenv('TWITTER_MONTHLY_LIMIT', '15000'))  # Basic plan limit
    
    # Logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE: Optional[str] = os.getenv('LOG_FILE')

    # ============================================================
    # E-14 Scraper Configuration
    # ============================================================

    # Scraper Workers
    SCRAPER_NUM_WORKERS: int = int(os.getenv('SCRAPER_NUM_WORKERS', '10'))
    SCRAPER_REQUESTS_PER_MINUTE: int = int(os.getenv('SCRAPER_REQUESTS_PER_MINUTE', '30'))
    SCRAPER_MAX_RETRIES: int = int(os.getenv('SCRAPER_MAX_RETRIES', '3'))
    SCRAPER_REQUEST_TIMEOUT: int = int(os.getenv('SCRAPER_REQUEST_TIMEOUT', '30'))

    # Scraper Target URL
    SCRAPER_BASE_URL: str = os.getenv(
        'SCRAPER_BASE_URL',
        'https://e14_congreso_2022.registraduria.gov.co'
    )

    # 2Captcha Configuration
    CAPTCHA_2_API_KEY: Optional[str] = os.getenv('CAPTCHA_2_API_KEY')
    CAPTCHA_SOLVER_ENABLED: bool = os.getenv('CAPTCHA_SOLVER_ENABLED', 'true').lower() == 'true'

    # Proxy Configuration
    USE_PROXY_ROTATION: bool = os.getenv('USE_PROXY_ROTATION', 'false').lower() == 'true'
    PROXY_LIST_FILE: Optional[str] = os.getenv('PROXY_LIST_FILE')

    # Scraper Output
    SCRAPER_OUTPUT_DIR: str = os.getenv('SCRAPER_OUTPUT_DIR', './output/e14_scraper')
    SCRAPER_SAVE_IMAGES: bool = os.getenv('SCRAPER_SAVE_IMAGES', 'true').lower() == 'true'

    # Legal RAG ("El Abogado")
    LEGAL_DATA_DIR: str = os.getenv(
        'LEGAL_DATA_DIR',
        str(Path(__file__).parent / 'data' / 'legal'),
    )
    LEGAL_RAG_DB_PATH: str = os.path.join(LEGAL_DATA_DIR, 'legal_rag_store.sqlite3')
    LEGAL_SOURCES_DIR: str = os.path.join(LEGAL_DATA_DIR, 'sources')
    LEGAL_RAG_TOP_K: int = int(os.getenv('LEGAL_RAG_TOP_K', '8'))
    LEGAL_RAG_TEMPERATURE: float = float(os.getenv('LEGAL_RAG_TEMPERATURE', '0.3'))

    # PND Topics (Plan Nacional de Desarrollo 2022-2026)
    PND_TOPICS: list = [
        'Seguridad',
        'Infraestructura',
        'Gobernanza y Transparencia',
        'Educación',
        'Salud',
        'Igualdad y Equidad',
        'Paz y Reinserción',
        'Economía y Empleo',
        'Medio Ambiente y Cambio Climático',
        'Alimentación'
    ]
    
    @classmethod
    def validate(cls) -> bool:
        """
        Validate that all required configuration is present.

        Returns:
            True if validation passes

        Raises:
            ValueError: If required configuration is missing
        """
        # SECURITY: Validate SECRET_KEY
        if not cls.SECRET_KEY:
            # Generate a temporary key for development only
            import secrets
            cls.SECRET_KEY = secrets.token_hex(32)
            import logging
            logging.warning("SECRET_KEY not set - generated temporary key. Set SECRET_KEY in production!")

        # Core required variables
        required_vars = [
            'DATABASE_URL',
        ]

        # External API keys (may be optional in dev, but recommended)
        api_keys = [
            'TWITTER_BEARER_TOKEN',
            'OPENAI_API_KEY',
        ]

        missing_required = [var for var in required_vars if not getattr(cls, var, None)]
        missing_api_keys = [var for var in api_keys if not getattr(cls, var, None)]

        if missing_required:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_required)}")

        if missing_api_keys:
            raise ValueError(f"Missing API keys (may cause service failures): {', '.join(missing_api_keys)}")

        return True


class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    TESTING = False

    @classmethod
    def validate(cls) -> bool:
        """
        Stricter validation for production environment.
        Fails hard if any secrets are missing.
        """
        # SECURITY: Validate SECRET_KEY length and presence
        if not cls.SECRET_KEY or len(cls.SECRET_KEY) < cls._SECRET_KEY_MIN_LENGTH:
            raise ValueError(
                f"SECRET_KEY must be set to a secure value (min {cls._SECRET_KEY_MIN_LENGTH} chars) in production"
            )

        # Validate JWT_SECRET_KEY
        if not cls.JWT_SECRET_KEY or len(cls.JWT_SECRET_KEY) < cls._SECRET_KEY_MIN_LENGTH:
            raise ValueError("JWT_SECRET_KEY must be set in production (min 32 chars)")

        # Validate all required secrets
        required_secrets = [
            'TWITTER_BEARER_TOKEN',
            'OPENAI_API_KEY',
            'DATABASE_URL',
        ]

        missing_secrets = [var for var in required_secrets if not getattr(cls, var, None)]
        if missing_secrets:
            raise ValueError(f"Missing required secrets in production: {', '.join(missing_secrets)}")

        return True


class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DEBUG = True
    TWITTER_BEARER_TOKEN = 'test-token'
    OPENAI_API_KEY = 'test-key'


# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
