"""
Schemas para el sistema de Testigos Electorales.
Registro via QR, notificaciones push y asignaciones.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
import re


# ============================================================
# ENUMS
# ============================================================

class WitnessStatus(str, Enum):
    """Estado del testigo."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    ASSIGNED = "ASSIGNED"
    BUSY = "BUSY"
    OFFLINE = "OFFLINE"
    INACTIVE = "INACTIVE"


class AssignmentStatus(str, Enum):
    """Estado de asignación."""
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    IN_TRANSIT = "IN_TRANSIT"
    ON_SITE = "ON_SITE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class NotificationType(str, Enum):
    """Tipo de notificación."""
    ASSIGNMENT = "ASSIGNMENT"
    ALERT = "ALERT"
    UPDATE = "UPDATE"
    REMINDER = "REMINDER"


# ============================================================
# PUSH SUBSCRIPTION
# ============================================================

class PushKeys(BaseModel):
    """Claves de push subscription."""
    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    """Web Push subscription object."""
    endpoint: str
    keys: PushKeys
    expirationTime: Optional[int] = None


# ============================================================
# QR CODE SCHEMAS
# ============================================================

class QRCodeGenerateRequest(BaseModel):
    """Request para generar código QR."""
    dept_code: Optional[str] = None
    muni_code: Optional[str] = None
    station_id: Optional[int] = None
    max_uses: int = Field(default=1, ge=1, le=100)
    expires_hours: Optional[int] = Field(default=72, ge=1, le=720)


class QRCodeResponse(BaseModel):
    """Respuesta con código QR generado."""
    success: bool = True
    code: str
    qr_url: str
    registration_url: str
    expires_at: Optional[datetime] = None
    max_uses: int


class QRCodeInfo(BaseModel):
    """Información de un código QR."""
    id: int
    code: str
    dept_code: Optional[str] = None
    muni_code: Optional[str] = None
    station_id: Optional[int] = None
    is_active: bool
    max_uses: int
    current_uses: int
    expires_at: Optional[datetime] = None
    created_at: datetime


# ============================================================
# WITNESS REGISTRATION
# ============================================================

class WitnessCoverage(BaseModel):
    """Zona de cobertura del testigo."""
    dept_code: str = Field(..., description="Código del departamento")
    dept_name: Optional[str] = None
    muni_code: Optional[str] = Field(None, description="Código del municipio")
    muni_name: Optional[str] = None
    station_id: Optional[int] = Field(None, description="ID del puesto de votación")
    station_name: Optional[str] = None
    zone_code: Optional[str] = Field(None, description="Código de zona")


class WitnessRegisterRequest(BaseModel):
    """Request para registro de testigo via QR."""
    qr_code: str = Field(..., description="Código del QR escaneado")
    full_name: str = Field(..., min_length=3, max_length=100)
    phone: str = Field(..., min_length=10, max_length=15)
    cedula: Optional[str] = Field(None, min_length=6, max_length=15)
    email: Optional[str] = None

    # Zona de cobertura
    coverage_dept_code: str = Field(..., description="Departamento que cubre")
    coverage_dept_name: Optional[str] = None
    coverage_muni_code: Optional[str] = Field(None, description="Municipio que cubre")
    coverage_muni_name: Optional[str] = None
    coverage_station_name: Optional[str] = Field(None, description="Puesto de votación que cubre")

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        # Limpiar y validar número colombiano
        clean = re.sub(r'[^\d]', '', v)
        if len(clean) < 10:
            raise ValueError('Número de teléfono inválido')
        return clean

    @field_validator('cedula')
    @classmethod
    def validate_cedula(cls, v):
        if v is None:
            return v
        clean = re.sub(r'[^\d]', '', v)
        if len(clean) < 6:
            raise ValueError('Cédula inválida')
        return clean


class WitnessRegisterResponse(BaseModel):
    """Respuesta de registro exitoso."""
    success: bool = True
    witness_id: int
    registration_code: str
    message: str = "Registro exitoso"
    push_prompt: bool = True  # Indicar al frontend que pida permiso de push


# ============================================================
# PUSH SUBSCRIPTION MANAGEMENT
# ============================================================

class PushSubscribeRequest(BaseModel):
    """Request para suscribir push notifications."""
    witness_id: int
    subscription: PushSubscription


class PushSubscribeResponse(BaseModel):
    """Respuesta de suscripción push."""
    success: bool = True
    message: str = "Notificaciones activadas"


class PushUnsubscribeRequest(BaseModel):
    """Request para desuscribir push."""
    witness_id: int


# ============================================================
# WITNESS DATA
# ============================================================

class WitnessBase(BaseModel):
    """Datos base de testigo."""
    full_name: str
    phone: str
    cedula: Optional[str] = None
    email: Optional[str] = None
    status: WitnessStatus = WitnessStatus.PENDING


class WitnessResponse(WitnessBase):
    """Respuesta con datos de testigo."""
    id: int
    registration_code: str
    push_enabled: bool = False
    current_lat: Optional[float] = None
    current_lon: Optional[float] = None
    current_zone: Optional[str] = None
    location_updated_at: Optional[datetime] = None

    # Zona de cobertura
    coverage_dept_code: Optional[str] = None
    coverage_dept_name: Optional[str] = None
    coverage_muni_code: Optional[str] = None
    coverage_muni_name: Optional[str] = None
    coverage_station_name: Optional[str] = None
    coverage_zone_code: Optional[str] = None

    registered_at: datetime
    last_active_at: Optional[datetime] = None


class WitnessListResponse(BaseModel):
    """Lista de testigos."""
    success: bool = True
    witnesses: List[WitnessResponse]
    total: int
    active_count: int
    push_enabled_count: int


class WitnessLocationUpdate(BaseModel):
    """Actualización de ubicación del testigo."""
    witness_id: int
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = None
    zone: Optional[str] = None


# ============================================================
# ASSIGNMENTS
# ============================================================

class AssignmentCreateRequest(BaseModel):
    """Request para crear asignación."""
    witness_id: int
    polling_table_id: int
    contest_id: int
    priority: int = Field(default=0, ge=0, le=10)
    reason: Optional[str] = None
    send_notification: bool = True


class AssignmentResponse(BaseModel):
    """Respuesta de asignación."""
    id: int
    witness_id: int
    witness_name: str
    polling_table_id: int
    mesa_id: str
    contest_id: int
    status: AssignmentStatus
    priority: int
    reason: Optional[str] = None
    assigned_at: datetime
    notified_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    arrived_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AssignmentUpdateRequest(BaseModel):
    """Request para actualizar estado de asignación."""
    status: AssignmentStatus
    notes: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


class AssignmentListResponse(BaseModel):
    """Lista de asignaciones."""
    success: bool = True
    assignments: List[AssignmentResponse]
    total: int
    pending_count: int
    active_count: int


# ============================================================
# NOTIFICATIONS
# ============================================================

class NotificationSendRequest(BaseModel):
    """Request para enviar notificación."""
    witness_ids: List[int] = Field(..., min_length=1)
    notification_type: NotificationType
    title: str = Field(..., min_length=1, max_length=100)
    body: str = Field(..., min_length=1, max_length=500)
    data: Optional[Dict[str, Any]] = None
    assignment_id: Optional[int] = None


class NotificationSendResponse(BaseModel):
    """Respuesta de envío de notificación."""
    success: bool = True
    sent_count: int
    failed_count: int
    failures: List[Dict[str, Any]] = Field(default_factory=list)


class NotificationResponse(BaseModel):
    """Notificación individual."""
    id: int
    witness_id: int
    assignment_id: Optional[int] = None
    notification_type: str
    title: str
    body: str
    sent_at: datetime
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    push_success: Optional[bool] = None


# ============================================================
# NEARBY WITNESSES
# ============================================================

class NearbyWitnessRequest(BaseModel):
    """Request para buscar testigos cercanos."""
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(default=5.0, ge=0.1, le=50)
    limit: int = Field(default=10, ge=1, le=50)
    status_filter: Optional[List[WitnessStatus]] = None


class NearbyWitness(BaseModel):
    """Testigo cercano."""
    id: int
    full_name: str
    phone: str
    distance_km: float
    status: WitnessStatus
    push_enabled: bool


class NearbyWitnessResponse(BaseModel):
    """Respuesta de testigos cercanos."""
    success: bool = True
    witnesses: List[NearbyWitness]
    total: int
    search_radius_km: float


# ============================================================
# VAPID CONFIG
# ============================================================

class VAPIDConfigResponse(BaseModel):
    """Configuración VAPID pública."""
    public_key: str
    subject: str


# ============================================================
# STATISTICS
# ============================================================

class WitnessStats(BaseModel):
    """Estadísticas de testigos."""
    total_registered: int = 0
    active: int = 0
    assigned: int = 0
    busy: int = 0
    offline: int = 0
    push_enabled: int = 0
    assignments_pending: int = 0
    assignments_completed_today: int = 0
