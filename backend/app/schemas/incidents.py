"""
Schemas para el sistema de incidentes del War Room.
Define tipos de incidente, severidades y estructuras de datos.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class IncidentType(str, Enum):
    """Tipos de incidentes del sistema electoral."""
    OCR_LOW_CONF = "OCR_LOW_CONF"           # Confianza OCR baja (<70%)
    ARITHMETIC_FAIL = "ARITHMETIC_FAIL"      # Sumas no cuadran
    E11_VS_URNA = "E11_VS_URNA"             # Sufragantes ≠ Votos urna
    RECOUNT_MARKED = "RECOUNT_MARKED"        # Mesa marcada recuento
    SIGNATURE_MISSING = "SIGNATURE_MISSING"  # Faltan firmas jurados
    RNEC_DELAY = "RNEC_DELAY"               # Sin publicación RNEC
    DISCREPANCY_RNEC = "DISCREPANCY_RNEC"   # Diferencia vs RNEC
    SOURCE_MISMATCH = "SOURCE_MISMATCH"      # Testigo ≠ Oficial


class IncidentSeverity(str, Enum):
    """Niveles de severidad de incidentes."""
    P0 = "P0"  # Crítico - SLA 10 min
    P1 = "P1"  # Alto - SLA 15 min
    P2 = "P2"  # Medio - SLA 30 min
    P3 = "P3"  # Bajo - SLA 60 min


class IncidentStatus(str, Enum):
    """Estados de un incidente."""
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    ESCALATED = "ESCALATED"


# Mapeo de tipo de incidente a severidad por defecto y SLA
INCIDENT_CONFIG = {
    IncidentType.ARITHMETIC_FAIL: {"default_severity": IncidentSeverity.P0, "sla_minutes": 10},
    IncidentType.DISCREPANCY_RNEC: {"default_severity": IncidentSeverity.P0, "sla_minutes": 10},
    IncidentType.RECOUNT_MARKED: {"default_severity": IncidentSeverity.P0, "sla_minutes": 10},
    IncidentType.OCR_LOW_CONF: {"default_severity": IncidentSeverity.P1, "sla_minutes": 15},
    IncidentType.E11_VS_URNA: {"default_severity": IncidentSeverity.P1, "sla_minutes": 15},
    IncidentType.SOURCE_MISMATCH: {"default_severity": IncidentSeverity.P1, "sla_minutes": 15},
    IncidentType.SIGNATURE_MISSING: {"default_severity": IncidentSeverity.P1, "sla_minutes": 20},
    IncidentType.RNEC_DELAY: {"default_severity": IncidentSeverity.P2, "sla_minutes": 30},
}


class IncidentBase(BaseModel):
    """Campos base de un incidente."""
    incident_type: IncidentType
    severity: IncidentSeverity
    mesa_id: str
    dept_code: str
    dept_name: Optional[str] = None
    muni_code: Optional[str] = None
    muni_name: Optional[str] = None
    puesto: Optional[str] = None
    description: str
    ocr_confidence: Optional[float] = None
    delta_value: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = None


class IncidentCreate(BaseModel):
    """Schema para crear un incidente."""
    incident_type: IncidentType
    severity: Optional[IncidentSeverity] = None  # Si no se provee, usa default del tipo
    mesa_id: str
    dept_code: str
    dept_name: Optional[str] = None
    muni_code: Optional[str] = None
    muni_name: Optional[str] = None
    puesto: Optional[str] = None
    description: str
    ocr_confidence: Optional[float] = None
    delta_value: Optional[float] = None
    evidence: Optional[Dict[str, Any]] = None


class Incident(IncidentBase):
    """Schema completo de un incidente."""
    id: int
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: datetime
    sla_deadline: datetime
    sla_remaining_minutes: Optional[int] = None
    assigned_to: Optional[str] = None
    assigned_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    escalated_to_legal: bool = False

    class Config:
        from_attributes = True


class IncidentAssignRequest(BaseModel):
    """Request para asignar un incidente."""
    user_id: str
    notes: Optional[str] = None


class IncidentResolveRequest(BaseModel):
    """Request para resolver un incidente."""
    resolution: str = Field(..., description="RESOLVED o FALSE_POSITIVE")
    notes: str


class IncidentEscalateRequest(BaseModel):
    """Request para escalar un incidente."""
    reason: str
    to_legal: bool = False


class IncidentListResponse(BaseModel):
    """Respuesta con lista de incidentes."""
    success: bool = True
    incidents: List[Incident]
    total: int
    open_count: int
    p0_count: int
    p1_count: int


class IncidentStats(BaseModel):
    """Estadísticas de incidentes."""
    total: int = 0
    by_severity: Dict[str, int] = Field(default_factory=lambda: {"P0": 0, "P1": 0, "P2": 0, "P3": 0})
    by_status: Dict[str, int] = Field(default_factory=lambda: {
        "OPEN": 0, "ASSIGNED": 0, "INVESTIGATING": 0,
        "RESOLVED": 0, "FALSE_POSITIVE": 0, "ESCALATED": 0
    })
    by_type: Dict[str, int] = Field(default_factory=dict)
    avg_resolution_time_minutes: Optional[float] = None
    sla_compliance_rate: Optional[float] = None


class IncidentStatsResponse(BaseModel):
    """Respuesta con estadísticas de incidentes."""
    success: bool = True
    stats: IncidentStats


# ============================================================
# KPIs del War Room
# ============================================================

class WarRoomKPIs(BaseModel):
    """KPIs principales del War Room."""
    mesas_total: int = 0
    mesas_testigo: int = 0
    mesas_rnec: int = 0
    mesas_reconciliadas: int = 0
    incidentes_p0: int = 0
    cobertura_pct: float = 0.0

    # Timeline progress
    testigo_pct: float = 0.0
    rnec_pct: float = 0.0
    reconciliadas_pct: float = 0.0

    # Timestamps
    last_rnec_update: Optional[datetime] = None
    last_testigo_update: Optional[datetime] = None


class TimelineProgress(BaseModel):
    """Progreso de publicación por fuente."""
    source: str  # WITNESS, OFFICIAL, RECONCILED
    processed: int
    total: int
    percentage: float
    last_update: Optional[datetime] = None


class WarRoomKPIsResponse(BaseModel):
    """Respuesta con KPIs del War Room."""
    success: bool = True
    kpis: WarRoomKPIs
    timeline: List[TimelineProgress] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)
