"""
Pydantic schemas for the Legal Intelligence Service ("El Abogado").
"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------

class LegalSourceType(str, Enum):
    LEY = "LEY"
    DECRETO = "DECRETO"
    JURISPRUDENCIA = "JURISPRUDENCIA"
    CONSTITUCION = "CONSTITUCION"
    CONCEPTO = "CONCEPTO"


class CaseStatus(str, Enum):
    DRAFT = "DRAFT"
    FILED = "FILED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    ARCHIVED = "ARCHIVED"


class CaseType(str, Enum):
    NULIDAD = "NULIDAD"
    RECONTEO = "RECONTEO"
    APELACION = "APELACION"
    OTRO = "OTRO"


class NoteType(str, Enum):
    GENERAL = "general"
    LEGAL_OPINION = "legal_opinion"
    STRATEGY = "strategy"
    DEADLINE_WARNING = "deadline_warning"


# ------------------------------------------------------------------
# Chat / Search
# ------------------------------------------------------------------

class LegalChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_history: Optional[List[Dict[str, str]]] = None
    top_k: int = Field(default=8, ge=1, le=30)
    source_filter: Optional[LegalSourceType] = None
    article_filter: Optional[str] = None


class LegalSourceRef(BaseModel):
    id: str = ""
    score: float = 0.0
    source_name: str = ""
    source_type: str = ""
    article: str = ""
    preview: str = ""


class LegalReference(BaseModel):
    source_name: str = ""
    source_type: str = ""
    article: str = ""
    section_type: str = ""
    score: float = 0.0


class LegalChatResponse(BaseModel):
    success: bool = True
    answer: str = ""
    sources: List[LegalSourceRef] = Field(default_factory=list)
    legal_references: List[LegalReference] = Field(default_factory=list)
    documents_retrieved: int = 0
    documents_indexed: int = 0


class LegalSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=8, ge=1, le=50)
    source_filter: Optional[LegalSourceType] = None
    article_filter: Optional[str] = None


class LegalClassifyRequest(BaseModel):
    incident: Dict[str, Any]


# ------------------------------------------------------------------
# Sources
# ------------------------------------------------------------------

class LegalSourceInfo(BaseModel):
    source_id: str
    source_name: str
    source_type: str
    chunks_count: int = 0
    uploaded_at: str = ""


# ------------------------------------------------------------------
# Case Management (LMS)
# ------------------------------------------------------------------

class CaseCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    case_type: CaseType = CaseType.NULIDAD
    description: str = ""
    corporacion: Optional[str] = None
    circunscripcion: Optional[str] = None
    linked_incident_ids: List[int] = Field(default_factory=list)


class CaseUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=500)
    status: Optional[CaseStatus] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class CaseNoteRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    author: str = Field(default="system", max_length=200)
    note_type: NoteType = NoteType.GENERAL


class CaseDocumentRequest(BaseModel):
    document_type: str = Field(default="ANEXO", max_length=50)
    title: str = Field(..., min_length=1, max_length=500)
    content: str = ""
    file_path: Optional[str] = None
    generated_by: str = "user"


class CaseIncidentRequest(BaseModel):
    incident_id: int


class CaseFromIncidentsRequest(BaseModel):
    incident_ids: List[int] = Field(..., min_items=1)
    case_type: CaseType = CaseType.NULIDAD
