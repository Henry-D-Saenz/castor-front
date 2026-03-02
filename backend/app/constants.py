"""
Application constants and configuration values.
Centralizes magic strings and configurable values.

SOLID: Single source of truth for configuration.
"""
from enum import Enum
from typing import Dict, List


# =============================================================================
# API CONFIGURATION
# =============================================================================

class APIConfig:
    """API-related constants."""
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    DEFAULT_RATE_LIMIT = "10 per minute"
    ANALYSIS_RATE_LIMIT = "5 per minute"
    CHAT_RATE_LIMIT = "15 per minute"


# =============================================================================
# PND TOPICS (Plan Nacional de Desarrollo)
# =============================================================================

class PNDTopics:
    """PND topic names - single source of truth."""
    SEGURIDAD = "Seguridad"
    EDUCACION = "Educación"
    SALUD = "Salud"
    ECONOMIA = "Economía y Empleo"
    INFRAESTRUCTURA = "Infraestructura"
    GOBERNANZA = "Gobernanza y Transparencia"
    IGUALDAD = "Igualdad y Equidad"
    PAZ = "Paz y Reinserción"
    AMBIENTE = "Medio Ambiente y Cambio Climático"
    ALIMENTACION = "Alimentación"
    TODOS = "Todos"

    @classmethod
    def all_topics(cls) -> List[str]:
        """Get all topic names."""
        return [
            cls.SEGURIDAD, cls.EDUCACION, cls.SALUD, cls.ECONOMIA,
            cls.INFRAESTRUCTURA, cls.GOBERNANZA, cls.IGUALDAD,
            cls.PAZ, cls.AMBIENTE, cls.ALIMENTACION
        ]

    @classmethod
    def main_topics(cls) -> List[str]:
        """Get main topics for analysis."""
        return [
            cls.SEGURIDAD, cls.EDUCACION, cls.SALUD,
            cls.ECONOMIA, cls.INFRAESTRUCTURA
        ]


# =============================================================================
# TOPIC KEYWORDS (for Twitter search)
# =============================================================================

TOPIC_KEYWORDS: Dict[str, str] = {
    PNDTopics.SEGURIDAD: "seguridad OR delincuencia OR crimen OR policía OR robo",
    PNDTopics.EDUCACION: "educación OR colegios OR universidad OR estudiantes OR maestros",
    PNDTopics.SALUD: "salud OR hospitales OR médicos OR EPS OR medicamentos",
    PNDTopics.ECONOMIA: "economía OR empleo OR trabajo OR desempleo OR empresas",
    PNDTopics.INFRAESTRUCTURA: "infraestructura OR vías OR carreteras OR transporte OR obras",
    PNDTopics.GOBERNANZA: "transparencia OR corrupción OR gobernanza OR gobierno",
    PNDTopics.IGUALDAD: "igualdad OR equidad OR género OR mujeres OR inclusión",
    PNDTopics.PAZ: "paz OR reinserción OR conflicto OR víctimas",
    PNDTopics.AMBIENTE: "medio ambiente OR cambio climático OR contaminación OR reciclaje",
    PNDTopics.ALIMENTACION: "alimentación OR comida OR hambre OR seguridad alimentaria OR agricultura",
}


# =============================================================================
# SENTIMENT CONFIGURATION
# =============================================================================

class SentimentConfig:
    """Sentiment analysis configuration."""
    DEFAULT_POSITIVE = 0.33
    DEFAULT_NEGATIVE = 0.33
    DEFAULT_NEUTRAL = 0.34

    # Thresholds for interpretation
    HIGH_THRESHOLD = 0.7
    MODERATE_THRESHOLD = 0.5
    LOW_THRESHOLD = 0.3

    # Labels
    LABELS = {
        "positive": "Positivo",
        "negative": "Negativo",
        "neutral": "Neutral"
    }


# =============================================================================
# CREDIBILITY SCORING (Bot Detection)
# =============================================================================

class CredibilityConfig:
    """Credibility scoring thresholds."""
    HIGH_CREDIBILITY = 0.7
    LOW_CREDIBILITY = 0.4

    # Account age thresholds (days)
    MIN_ACCOUNT_AGE = 7
    ESTABLISHED_ACCOUNT_AGE = 30
    OLD_ACCOUNT_AGE = 365

    # Follower thresholds
    MIN_FOLLOWERS = 1
    MEDIUM_FOLLOWERS = 100
    HIGH_FOLLOWERS = 1000

    # Username validation
    MAX_NUMERIC_CHARS = 6


# =============================================================================
# CACHE CONFIGURATION
# =============================================================================

class CacheConfig:
    """Cache TTL values (in seconds)."""
    TWITTER_TTL = 86400        # 24 hours
    SENTIMENT_TTL = 86400      # 24 hours
    OPENAI_TTL = 43200         # 12 hours
    TRENDING_TTL = 21600       # 6 hours
    DEFAULT_TTL = 3600         # 1 hour


# =============================================================================
# RESPONSE MESSAGES
# =============================================================================

class Messages:
    """User-facing messages."""
    # Errors
    INVALID_REQUEST = "Datos de solicitud inválidos"
    LOCATION_REQUIRED = "La ubicación es requerida"
    INVALID_LOCATION = "Formato de ubicación inválido"
    NO_TWEETS_FOUND = "No se encontraron tweets para la ubicación y tema especificados"
    SERVICE_UNAVAILABLE = "Servicios de análisis no disponibles"
    INTERNAL_ERROR = "Error interno del servidor"
    RATE_LIMIT_EXCEEDED = "Límite de solicitudes excedido"

    # Success
    ANALYSIS_COMPLETE = "Análisis completado exitosamente"
    DATA_SAVED = "Datos guardados correctamente"

    # Info
    NO_DATA_AVAILABLE = "No hay datos disponibles para los parámetros especificados"
    PROCESSING = "Procesando solicitud..."


# =============================================================================
# COLOMBIAN LOCATIONS
# =============================================================================

COLOMBIAN_DEPARTMENTS = [
    "Amazonas", "Antioquia", "Arauca", "Atlántico", "Bogotá",
    "Bolívar", "Boyacá", "Caldas", "Caquetá", "Casanare",
    "Cauca", "Cesar", "Chocó", "Córdoba", "Cundinamarca",
    "Guainía", "Guaviare", "Huila", "La Guajira", "Magdalena",
    "Meta", "Nariño", "Norte de Santander", "Putumayo", "Quindío",
    "Risaralda", "San Andrés", "Santander", "Sucre", "Tolima",
    "Valle del Cauca", "Vaupés", "Vichada"
]

MAJOR_CITIES = [
    "Bogotá", "Medellín", "Cali", "Barranquilla", "Cartagena",
    "Bucaramanga", "Pereira", "Santa Marta", "Ibagué", "Cúcuta",
    "Villavicencio", "Manizales", "Pasto", "Neiva", "Armenia"
]


# =============================================================================
# OPENAI PROMPTS (Templates)
# =============================================================================

class PromptTemplates:
    """OpenAI prompt templates."""

    EXECUTIVE_SUMMARY_SYSTEM = """Eres un analista político experto en Colombia.
Genera resúmenes ejecutivos basados en análisis de sentimiento de redes sociales.
Responde siempre en JSON con la estructura especificada."""

    STRATEGIC_PLAN_SYSTEM = """Eres un estratega político experto en campañas electorales en Colombia.
Genera planes estratégicos basados en análisis de sentimiento de redes sociales.
Responde siempre en JSON con la estructura especificada."""

    SPEECH_SYSTEM = """Eres un escritor de discursos políticos experto en Colombia.
Genera discursos inspiradores y conectados con las preocupaciones ciudadanas.
Responde siempre en JSON con la estructura especificada."""

    MEDIA_SUMMARY_SYSTEM = """Eres un analista de medios neutral y objetivo.
Genera resúmenes de conversación en redes sociales sin sesgo político.
Responde siempre en JSON con la estructura especificada."""


# =============================================================================
# FEATURE FLAGS
# =============================================================================

class FeatureFlags:
    """Feature flags for gradual rollout."""
    BOT_DETECTION_ENABLED = True
    WEIGHTED_SENTIMENT_ENABLED = True
    RAG_INDEXING_ENABLED = True
    ASYNC_ANALYSIS_ENABLED = True
    WHATSAPP_NOTIFICATIONS_ENABLED = False  # Disabled after Twilio removal
