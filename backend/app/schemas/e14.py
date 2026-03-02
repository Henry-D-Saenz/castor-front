"""
Schemas para E-14 (Acta de Escrutinio de Jurados de Votación).
Estructura basada en el formulario oficial de la Registraduría Nacional de Colombia.

Schema v2 - Consulta 8 Marzo 2026 + Multi-página support
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator


# ============================================================
# ENUMS BASE
# ============================================================

class CopyType(str, Enum):
    """Tipo de copia del E-14."""
    CLAVEROS = "CLAVEROS"
    DELEGADOS = "DELEGADOS"
    TRANSMISION = "TRANSMISION"


class ListType(str, Enum):
    """Tipo de lista electoral."""
    CON_VOTO_PREFERENTE = "CON_VOTO_PREFERENTE"
    SIN_VOTO_PREFERENTE = "SIN_VOTO_PREFERENTE"


class CircunscripcionType(str, Enum):
    """Tipo de circunscripción."""
    TERRITORIAL = "TERRITORIAL"
    ESPECIAL_INDIGENA = "ESPECIAL_INDIGENA"
    ESPECIAL_AFRO = "ESPECIAL_AFRO"


class Corporacion(str, Enum):
    """Corporación electoral."""
    CAMARA = "CAMARA"
    SENADO = "SENADO"
    PRESIDENCIA = "PRESIDENCIA"
    GOBERNACION = "GOBERNACION"
    ALCALDIA = "ALCALDIA"
    ASAMBLEA = "ASAMBLEA"
    CONCEJO = "CONCEJO"
    JAL = "JAL"
    CONSULTA = "CONSULTA"


class ValidationSeverity(str, Enum):
    """Severidad de validación."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ============================================================
# ENUMS V2 - Payload Schema v2
# ============================================================

class ProcessType(str, Enum):
    """Tipo de proceso electoral."""
    NACIONAL = "NACIONAL"
    TERRITORIAL = "TERRITORIAL"
    CONSULTA = "CONSULTA"


class ContestType(str, Enum):
    """Tipo de contienda."""
    PRESIDENCY = "PRESIDENCY"
    SENATE = "SENATE"
    CHAMBER = "CHAMBER"
    GOVERNOR = "GOVERNOR"
    MAYOR = "MAYOR"
    ASSEMBLY = "ASSEMBLY"
    COUNCIL = "COUNCIL"
    JAL = "JAL"
    CONSULTA = "CONSULTA"


class ContestScope(str, Enum):
    """Alcance de la contienda."""
    NATIONAL = "NATIONAL"
    DEPARTMENTAL = "DEPARTMENTAL"
    MUNICIPAL = "MUNICIPAL"
    LOCAL = "LOCAL"


class BallotOptionType(str, Enum):
    """Tipo de opción en la boleta - v2."""
    CANDIDATE = "CANDIDATE"           # Candidato único (Presidencia, Gobernador, Alcalde)
    LIST_ONLY = "LIST_ONLY"           # Voto solo por lista (renglón 0)
    LIST_CANDIDATE = "LIST_CANDIDATE" # Voto preferente por candidato de lista
    BLANK = "BLANK"                   # Voto en blanco
    NULL = "NULL"                     # Voto nulo
    UNMARKED = "UNMARKED"             # Tarjeta no marcada
    TOTAL = "TOTAL"                   # Total de votos


class SourceType(str, Enum):
    """Origen del documento."""
    WITNESS_UPLOAD = "WITNESS_UPLOAD"    # Subido por testigo electoral
    REGISTRADURIA = "REGISTRADURIA"      # Desde portal de Registraduría
    MANUAL_ENTRY = "MANUAL_ENTRY"        # Digitación manual


# ============================================================
# V2 SCHEMAS - Pipeline Context
# ============================================================

class TargetProcess(BaseModel):
    """Contexto del proceso electoral objetivo."""
    process_type: ProcessType
    process_date: str = Field(..., description="YYYY-MM-DD")
    contest_type: ContestType
    contest_scope: ContestScope


class PipelineContext(BaseModel):
    """Contexto del pipeline de procesamiento."""
    target_process: TargetProcess
    template_family: str = Field("E14", description="Familia de plantilla")
    template_version: str = Field(..., description="Versión específica: E14_CONSULTA_V1, E14_ASAMBLEA_MULTIPAGINA_V1")
    ruleset_version: str = Field("VALIDATION_CORE_V1", description="Versión del conjunto de reglas")


# ============================================================
# V2 SCHEMAS - Input Document
# ============================================================

class PageInfo(BaseModel):
    """Información de una página del documento."""
    page_no: int = Field(..., ge=1)
    page_image_uri: Optional[str] = Field(None, description="URI de la imagen de página")
    page_sha256: Optional[str] = None
    political_group_code: Optional[str] = Field(None, description="HEADER, 0001, 0002, FIRMAS, etc.")
    description: Optional[str] = None


class InputDocument(BaseModel):
    """Documento de entrada."""
    source_file: str
    form_type: str = "E14"
    copy_type: CopyType
    source_type: SourceType
    object_uri: Optional[str] = Field(None, description="URI del objeto en storage")
    sha256: str
    total_pages: int = Field(..., ge=1)
    pages: List[PageInfo] = Field(default_factory=list)


# ============================================================
# V2 SCHEMAS - Document Header
# ============================================================

class DocumentHeaderExtracted(BaseModel):
    """Encabezado del documento extraído por OCR."""
    reported_election_date: str
    reported_election_label: str
    corporacion: Corporacion
    dept_code: str
    dept_name: str
    muni_code: str
    muni_name: str
    zone_code: str
    station_code: str
    table_number: int
    place_name: Optional[str] = None
    page_count_reported: Optional[int] = None

    @property
    def mesa_id(self) -> str:
        """Genera ID único de mesa: DEPT-MUNI-ZONA-PUESTO-MESA."""
        return f"{self.dept_code}-{self.muni_code}-{self.zone_code}-{self.station_code}-{self.table_number:03d}"


# ============================================================
# V2 SCHEMAS - OCR Fields
# ============================================================

class OCRField(BaseModel):
    """Campo extraído por OCR - v2 con soporte para raw_mark."""
    field_key: str = Field(..., description="Clave del campo: TOTAL_SUFRAGANTES_E11, CANDIDATE_51, etc.")
    page_no: int = Field(..., ge=1)

    # Valor extraído
    value_int: Optional[int] = None
    value_bool: Optional[bool] = None
    raw_text: Optional[str] = None
    raw_mark: Optional[str] = Field(None, description="Marca especial: *, **, ***")

    # Contexto del campo
    ballot_option_type: Optional[BallotOptionType] = None
    political_group_code: Optional[str] = None
    political_group_name: Optional[str] = None
    candidate_ordinal: Optional[int] = None
    candidate_name: Optional[str] = None
    list_type: Optional[ListType] = None

    # Metadata OCR
    confidence: float = Field(0.0, ge=0, le=1)
    needs_review: bool = False
    notes: Optional[str] = None


# ============================================================
# V2 SCHEMAS - Normalized Tallies
# ============================================================

class TallyEntry(BaseModel):
    """Entrada de conteo normalizado."""
    subject_type: BallotOptionType
    candidate_ordinal: Optional[int] = None
    votes: int = Field(..., ge=0)


class PoliticalGroupTally(BaseModel):
    """Conteo normalizado por grupo político."""
    political_group_code: str
    tallies: List[TallyEntry]
    party_total: int = Field(..., ge=0)


class SpecialsTally(BaseModel):
    """Conteo de votos especiales."""
    specials: List[TallyEntry]


# ============================================================
# V2 SCHEMAS - Validations
# ============================================================

class ValidationDetail(BaseModel):
    """Detalles de validación."""
    # Campos dinámicos según la regla
    class Config:
        extra = "allow"


class ValidationResultV2(BaseModel):
    """Resultado de validación v2."""
    rule_key: str
    passed: bool
    severity: ValidationSeverity
    details: Optional[Dict[str, Any]] = None


# ============================================================
# V2 SCHEMAS - DB Write Plan
# ============================================================

class AlertRow(BaseModel):
    """Alerta a insertar."""
    type: str
    severity: ValidationSeverity
    status: str = "OPEN"
    evidence: Optional[Dict[str, Any]] = None


class DBWritePlan(BaseModel):
    """Plan de escritura a base de datos."""
    form_instance: Dict[str, Any]
    form_page_rows: str
    ocr_field_rows: str
    vote_tally_rows: str
    validation_result_rows: str
    alert_rows: List[AlertRow] = Field(default_factory=list)


# ============================================================
# V2 PAYLOAD PRINCIPAL
# ============================================================

class E14PayloadV2(BaseModel):
    """
    Payload completo v2 para evento ocr.completed.
    Compatible con schema de BD v2 (migrations/002_electoral_schema_v2.sql).
    """
    event_type: Literal["ocr.completed"] = "ocr.completed"
    schema_version: str = Field("1.2.0", description="Versión del schema del payload")
    produced_at: datetime = Field(default_factory=datetime.utcnow)

    # Contexto del pipeline
    pipeline_context: PipelineContext

    # Documento de entrada
    input_document: InputDocument

    # Datos extraídos
    document_header_extracted: DocumentHeaderExtracted
    ocr_fields: List[OCRField]

    # Conteos normalizados
    normalized_tallies: List[Union[PoliticalGroupTally, SpecialsTally, Dict[str, Any]]]

    # Validaciones
    validations: List[ValidationResultV2]

    # Plan de escritura a BD
    db_write_plan: DBWritePlan

    # Metadata adicional
    meta: Optional[Dict[str, Any]] = Field(None, description="Metadata adicional del procesamiento")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + "Z"
        }


# ============================================================
# Sub-schemas para extracción OCR
# ============================================================

class E14Header(BaseModel):
    """Encabezado del E-14 extraído por OCR."""
    barcode: Optional[str] = Field(None, description="Código de barras único del formulario")
    version: Optional[str] = Field(None, description="Versión del formulario")
    page_info: Optional[str] = Field(None, description="Info de página (ej: 'Pag: 01 de 09')")
    copy_type: CopyType = Field(..., description="Tipo de copia: CLAVEROS, DELEGADOS, TRANSMISION")
    election_name: Optional[str] = Field(None, description="Nombre de la elección")
    election_date: Optional[str] = Field(None, description="Fecha de la elección")
    corporacion: Corporacion = Field(..., description="Corporación: CAMARA, SENADO, etc.")

    # Ubicación geográfica
    departamento_code: str = Field(..., description="Código departamento (ej: '01')")
    departamento_name: str = Field(..., description="Nombre departamento (ej: 'ANTIOQUIA')")
    municipio_code: str = Field(..., description="Código municipio (ej: '001')")
    municipio_name: str = Field(..., description="Nombre municipio (ej: 'MEDELLIN')")
    lugar: Optional[str] = Field(None, description="Nombre del lugar de votación")
    zona: str = Field(..., description="Código de zona (ej: '01')")
    puesto: str = Field(..., description="Código de puesto (ej: '01')")
    mesa: str = Field(..., description="Número de mesa (ej: '001')")

    # Identificador único compuesto
    @property
    def mesa_id(self) -> str:
        """Genera ID único de mesa: DEPT-MUNI-ZONA-PUESTO-MESA."""
        return f"{self.departamento_code}-{self.municipio_code}-{self.zona}-{self.puesto}-{self.mesa}"


class NivelacionMesa(BaseModel):
    """Nivelación de la mesa - totales de control."""
    total_sufragantes_e11: int = Field(..., description="Total sufragantes según E-11")
    total_votos_urna: int = Field(..., description="Total votos encontrados en urna")
    total_votos_incinerados: Optional[int] = Field(None, description="Votos incinerados (si aplica)")

    # Confidence scores del OCR
    confidence_sufragantes: Optional[float] = Field(None, ge=0, le=1)
    confidence_urna: Optional[float] = Field(None, ge=0, le=1)
    confidence_incinerados: Optional[float] = Field(None, ge=0, le=1)


class CandidateVotes(BaseModel):
    """Votos por candidato individual (para listas con voto preferente)."""
    candidate_number: str = Field(..., description="Número del candidato (ej: '101', '102')")
    votes: int = Field(..., ge=0, description="Votos del candidato")
    confidence: Optional[float] = Field(None, ge=0, le=1, description="Confianza OCR")
    needs_review: bool = Field(False, description="Requiere revisión humana")


class PartyVotes(BaseModel):
    """Votos por partido/agrupación política."""
    party_code: str = Field(..., description="Código del partido (ej: '0302')")
    party_name: str = Field(..., description="Nombre del partido")
    party_logo_detected: bool = Field(False, description="Si se detectó el logo")
    list_type: ListType = Field(..., description="Tipo de lista")
    circunscripcion: CircunscripcionType = Field(CircunscripcionType.TERRITORIAL)

    # Votos
    votos_agrupacion: int = Field(0, ge=0, description="Votos solo por la agrupación")
    votos_candidatos: List[CandidateVotes] = Field(default_factory=list, description="Votos por candidato")
    total_votos: int = Field(..., ge=0, description="Total = votos_agrupacion + sum(votos_candidatos)")

    # OCR metadata
    confidence_total: Optional[float] = Field(None, ge=0, le=1)
    needs_review: bool = Field(False)

    @field_validator('total_votos', mode='before')
    @classmethod
    def calculate_total(cls, v, info):
        """Calcula el total si no se proporciona."""
        if v is not None:
            return v
        data = info.data if hasattr(info, 'data') else {}
        agrupacion = data.get('votos_agrupacion', 0)
        candidatos = data.get('votos_candidatos', [])
        return agrupacion + sum(c.votes for c in candidatos)


class VotosEspeciales(BaseModel):
    """Votos en blanco, nulos y no marcados."""
    votos_blanco: int = Field(0, ge=0)
    votos_nulos: int = Field(0, ge=0)
    votos_no_marcados: int = Field(0, ge=0)

    confidence_blanco: Optional[float] = Field(None, ge=0, le=1)
    confidence_nulos: Optional[float] = Field(None, ge=0, le=1)
    confidence_no_marcados: Optional[float] = Field(None, ge=0, le=1)

    @property
    def total(self) -> int:
        return self.votos_blanco + self.votos_nulos + self.votos_no_marcados


class ConstanciasMesa(BaseModel):
    """Constancias y firmas del escrutinio de mesa."""
    hubo_recuento: Optional[bool] = Field(None, description="¿Hubo recuento de votos?")
    recuento_solicitado_por: Optional[str] = Field(None)
    recuento_en_representacion_de: Optional[str] = Field(None)
    otras_constancias: Optional[str] = Field(None, description="Texto de otras constancias")

    # Firmas de jurados
    num_jurados_firmantes: int = Field(0, ge=0, le=6, description="Cantidad de jurados que firmaron")
    jurados_info: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Info de jurados (sin datos personales sensibles)"
    )


# ============================================================
# Schema principal de extracción E-14
# ============================================================

class E14ExtractionResult(BaseModel):
    """Resultado completo de extracción OCR de un E-14."""

    # Metadata de procesamiento
    extraction_id: str = Field(..., description="ID único de esta extracción")
    source_file: str = Field(..., description="Nombre/URI del archivo fuente")
    source_sha256: str = Field(..., description="Hash SHA256 del archivo")
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    model_version: str = Field(..., description="Versión del modelo OCR usado")
    processing_time_ms: Optional[int] = Field(None, description="Tiempo de procesamiento en ms")

    # Datos extraídos
    header: E14Header
    nivelacion: NivelacionMesa
    partidos: List[PartyVotes] = Field(default_factory=list)
    votos_especiales: VotosEspeciales
    constancias: Optional[ConstanciasMesa] = None

    # Métricas de confianza global
    overall_confidence: float = Field(..., ge=0, le=1, description="Confianza promedio global")
    fields_needing_review: int = Field(0, ge=0, description="Cantidad de campos que necesitan revisión")

    # Páginas procesadas
    total_pages: int = Field(..., ge=1)
    pages_processed: int = Field(..., ge=1)

    @property
    def total_votos_partidos(self) -> int:
        """Suma de todos los votos de partidos."""
        return sum(p.total_votos for p in self.partidos)

    @property
    def total_computado(self) -> int:
        """Total computado: partidos + especiales."""
        return self.total_votos_partidos + self.votos_especiales.total


# ============================================================
# Schemas de validación
# ============================================================

class ValidationRule(BaseModel):
    """Regla de validación."""
    rule_id: str
    rule_name: str
    description: str


class ValidationResult(BaseModel):
    """Resultado de una validación específica."""
    rule_id: str
    rule_name: str
    passed: bool
    severity: ValidationSeverity
    message: str
    expected_value: Optional[int] = None
    actual_value: Optional[int] = None
    delta: Optional[int] = None
    details: Optional[Dict] = None


class E14ValidationReport(BaseModel):
    """Reporte completo de validación de un E-14."""
    extraction_id: str
    mesa_id: str
    validated_at: datetime = Field(default_factory=datetime.utcnow)

    # Resultados
    validations: List[ValidationResult]
    all_passed: bool
    critical_failures: int = 0
    high_failures: int = 0
    medium_failures: int = 0
    low_failures: int = 0

    # Alertas generadas
    alerts_generated: List[str] = Field(default_factory=list)


# ============================================================
# Schemas de request/response API
# ============================================================

class E14ProcessRequest(BaseModel):
    """Request para procesar un E-14."""
    file_url: Optional[str] = Field(None, description="URL del PDF a procesar")
    # file_base64: Optional[str] = Field(None, description="PDF en base64")
    election_id: Optional[str] = Field(None, description="ID de la elección")
    force_reprocess: bool = Field(False, description="Forzar reprocesamiento si ya existe")


class E14ProcessResponse(BaseModel):
    """Response del procesamiento de E-14."""
    success: bool
    extraction_id: str
    mesa_id: str

    # Resumen rápido
    total_sufragantes: int
    total_urna: int
    total_computado: int
    delta: int  # Diferencia urna vs computado

    # Validación
    validation_passed: bool
    alerts_count: int
    fields_needing_review: int

    # Datos completos
    extraction: Optional[E14ExtractionResult] = None
    validation_report: Optional[E14ValidationReport] = None

    # Errores si los hay
    error_message: Optional[str] = None


class E14BatchProcessRequest(BaseModel):
    """Request para procesar múltiples E-14."""
    file_urls: List[str] = Field(..., min_items=1, max_items=100)
    election_id: str
    parallel: bool = Field(True, description="Procesar en paralelo")


class E14BatchProcessResponse(BaseModel):
    """Response del procesamiento batch."""
    success: bool
    total_requested: int
    total_processed: int
    total_failed: int
    results: List[E14ProcessResponse]
