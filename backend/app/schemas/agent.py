"""
Schemas for the Electoral Intelligence Agent API.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class AgentStatus(str, Enum):
    """Agent operational status."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class HITLStatus(str, Enum):
    """HITL request status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


# ============================================================
# Request Schemas
# ============================================================

class AgentConfigUpdateRequest(BaseModel):
    """Request to update agent configuration."""
    E14_POLL_INTERVAL: Optional[int] = Field(None, ge=5, le=300)
    INCIDENT_POLL_INTERVAL: Optional[int] = Field(None, ge=5, le=120)
    OCR_CONFIDENCE_THRESHOLD: Optional[float] = Field(None, ge=0.0, le=1.0)
    GEOGRAPHIC_CLUSTER_THRESHOLD: Optional[int] = Field(None, ge=2)
    AUTO_INCIDENT_CREATION: Optional[bool] = None
    AUTO_LEGAL_CLASSIFICATION: Optional[bool] = None
    LLM_BRIEFINGS_ENABLED: Optional[bool] = None


class HITLApproveRequest(BaseModel):
    """Request to approve a HITL request."""
    notes: Optional[str] = Field(None, max_length=1000)


class HITLRejectRequest(BaseModel):
    """Request to reject a HITL request."""
    notes: str = Field(..., min_length=10, max_length=1000)


class ProcessE14Request(BaseModel):
    """Request to process an E-14 form."""
    form_data: Dict[str, Any]


# ============================================================
# Response Schemas
# ============================================================

class AgentMetricsResponse(BaseModel):
    """Agent metrics response."""
    anomalies_detected_total: int = 0
    anomalies_detected_last_hour: int = 0
    incidents_auto_created: int = 0
    detection_latency_p95_ms: float = 0.0
    false_positive_rate: float = 0.0
    cpaca_classifications_total: int = 0
    deadline_alerts_sent: int = 0
    uptime_seconds: int = 0
    actions_total: int = 0
    hitl_pending: int = 0
    briefings_generated: int = 0
    last_briefing_at: Optional[str] = None


class AgentStatusResponse(BaseModel):
    """Agent status response."""
    success: bool = True
    status: AgentStatus
    started_at: Optional[str] = None
    uptime_seconds: int = 0
    metrics: AgentMetricsResponse


class AgentHealthResponse(BaseModel):
    """Agent health check response."""
    healthy: bool
    status: AgentStatus
    timestamp: str


class ActionRecord(BaseModel):
    """Record of an agent action."""
    action_id: str
    action_type: str
    timestamp: str
    trigger_rule: str
    target_id: Optional[str] = None
    target_type: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    hitl_required: bool = False
    hitl_status: Optional[str] = None
    result: Optional[str] = None
    error: Optional[str] = None


class ActionsListResponse(BaseModel):
    """List of agent actions response."""
    success: bool = True
    actions: List[ActionRecord]
    total: int


class HITLRequest(BaseModel):
    """HITL approval request."""
    request_id: str
    action_type: str
    created_at: str
    expires_at: str
    priority: str
    title: str
    description: str
    context: Dict[str, Any] = Field(default_factory=dict)
    recommended_action: Optional[str] = None
    status: HITLStatus = HITLStatus.PENDING
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None
    review_notes: Optional[str] = None


class HITLListResponse(BaseModel):
    """List of HITL requests response."""
    success: bool = True
    requests: List[HITLRequest]
    total: int
    pending_count: int


class HITLActionResponse(BaseModel):
    """Response from HITL action (approve/reject)."""
    success: bool
    request: Optional[HITLRequest] = None
    error: Optional[str] = None


class BriefingSection(BaseModel):
    """Section of an intelligence briefing."""
    title: str
    content: Any


class BriefingResponse(BaseModel):
    """Intelligence briefing response."""
    success: bool = True
    type: str = "HOURLY_BRIEFING"
    generated_at: str
    period: str
    narrative: str
    sections: Dict[str, Any] = Field(default_factory=dict)
    generation_latency_seconds: Optional[float] = None


class AgentConfigResponse(BaseModel):
    """Agent configuration response."""
    success: bool = True
    config: Dict[str, Any]


class StartStopResponse(BaseModel):
    """Response from start/stop operations."""
    success: bool
    status: AgentStatus
    message: Optional[str] = None


# ============================================================
# KPI Schemas
# ============================================================

class KPITarget(BaseModel):
    """KPI with target."""
    value: float
    target: float
    on_target: bool
    gap: float
    gap_percent: float


class KPIStatusResponse(BaseModel):
    """KPI status against targets response."""
    success: bool = True
    kpis: Dict[str, KPITarget]
    timestamp: str
