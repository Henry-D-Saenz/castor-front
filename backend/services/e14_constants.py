"""
E14 Constants — Single source of truth for all E-14 validation thresholds,
business rules, and shared utilities.

Used by: e14_validator, e14_corrections, e14_analytics, e14_json_store,
         e14_pmsn_rules, ocr_agents/*, agent/analyzers/anomaly_detector.
"""
from typing import Any, Dict, List


# ── Mesa limits ──────────────────────────────────────────────────────
MAX_VOTES_PER_MESA = 800
MIN_ANCHOR = 1
MAX_ANCHOR = 800

# ── Arithmetic reconciliation ────────────────────────────────────────
ARITH_TOLERANCE = 0        # Strict: sum must equal total exactly
ARITH_WARN_TOL = 2         # WARN band: 1 <= |diff| <= 2 (handwriting noise)

# ── Arithmetic delta → review priority (for HITL escalation) ────────
ARITH_DELTA_CRITICAL = 50  # |diff| > 50  → CRITICAL review
ARITH_DELTA_HIGH = 20      # |diff| > 20  → HIGH review
ARITH_DELTA_MEDIUM = 5     # |diff| > 5   → MEDIUM review
                           # |diff| <= 5  → LOW review

# ── Three-way leveling ───────────────────────────────────────────────
LEVELING_TOLERANCE = 2     # Soft: suf ↔ urna ↔ total allows ±2

# ── Pre-validation gate ──────────────────────────────────────────────
PRE_GATE_DIFF_THRESHOLD = 0.5  # 50% of total_votos

# ── Statistical plausibility ─────────────────────────────────────────
MAX_BLANCOS_PCT = 25.0
MAX_NULOS_PCT = 10.0
REPEATED_CONSTANT_THRESHOLD = 3
CODE_AS_VOTES_THRESHOLD = 200

# ── OCR confidence ───────────────────────────────────────────────────
REOCR_CONFIDENCE_THRESHOLD = 0.70

# ── Dashboard OCR confidence risk brackets ───────────────────────────
# Used by: e14_analytics, e14_json_store, frontend JS
OCR_HIGH_RISK_THRESHOLD = 0.70    # confidence < 0.70  → HIGH_RISK
OCR_MEDIUM_RISK_THRESHOLD = 0.85  # 0.70 <= conf < 0.85 → MEDIUM_RISK
                                  # conf >= 0.85        → LOW_RISK
# Anomaly classification thresholds (for get_anomalies)
ANOMALY_HIGH_RISK_THRESHOLD = 0.60   # conf < 0.60  → high_risk
ANOMALY_NEEDS_REVIEW_DEFAULT = 0.75  # conf < 0.75  → needs_review

# ── Confidence penalty table ─────────────────────────────────────────
CONFIDENCE_PENALTIES: Dict[str, float] = {
    "HC-03_FAIL": -0.25,
    "NIV-01_FAIL": -0.20,
    "ARITH_FAIL": -0.15,
    "ARITH_WARN": -0.05,
    "OCR_LOW_CONF": -0.15,
    "CRITICAL_NULL": -0.15,
}

# ── Severity mappings ────────────────────────────────────────────────
# Used by: anomaly_detector, incident_creator, legal_document_generator
SEVERITY_TO_PRIORITY: Dict[str, str] = {
    "CRITICAL": "P0",
    "HIGH": "P1",
    "MEDIUM": "P2",
    "LOW": "P3",
}

SEVERITY_WEIGHT: Dict[str, int] = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}

# ── Anomaly type weights (for risk scoring) ──────────────────────────
ANOMALY_TYPE_WEIGHTS: Dict[str, float] = {
    "ARITHMETIC_MISMATCH": 1.0,
    "E11_URNA_MISMATCH": 0.9,
    "GEOGRAPHIC_CLUSTER": 0.95,
    "IMPOSSIBLE_VALUE": 0.85,
    "SIGNATURE_MISSING": 0.7,
    "STATISTICAL_OUTLIER": 0.6,
    "TEMPORAL_ANOMALY": 0.5,
    "OCR_LOW_CONFIDENCE": 0.4,
    "DUPLICATE_FORM": 0.3,
}

# ── Department aliases (OCR often returns abbreviated names) ────────
_DEPT_ALIASES: Dict[str, str] = {
    "VALLE":              "VALLE DEL CAUCA",
    "NORTE SANTANDER":    "NORTE DE SANTANDER",
    "N DE SANTANDER":     "NORTE DE SANTANDER",
    "BOGOTA D.C.":        "BOGOTA",
    "BOGOTA DC":          "BOGOTA",
    "BOGOTA D C":         "BOGOTA",
    "D.C.":               "BOGOTA",
    "SAN ANDRES PROVIDENCIA": "SAN ANDRES",
    "NARI\u00d1O":        "NARINO",
    "NARIÑO":             "NARINO",
    "GUAJIRA":            "LA GUAJIRA",
}

# ── Municipios objetivo (scope del dashboard y reglas de negocio) ────
# Normalized: uppercase, no accents. Key = dept, value = set of munis.
MUNICIPIOS_OBJETIVO: Dict[str, set] = {
    "AMAZONAS": {"LETICIA"},
    "ANTIOQUIA": {
        "MEDELLIN", "ENVIGADO", "BELLO", "RIONEGRO", "ITAGUI",
        "SABANETA", "LA CEJA", "EL RETIRO", "CALDAS", "SONSON",
        "MARINILLA", "COPACABANA", "LA ESTRELLA", "GUARNE",
        "CARMEN DE VIBORAL", "CONCORDIA", "APARTADO",
        "SANTA ROSA DE OSOS", "TURBO", "GIRARDOTA", "SANTUARIO",
    },
    "ARAUCA": {"ARAUCA", "TAME", "SARAVENA"},
    "ATLANTICO": {"BARRANQUILLA", "SOLEDAD", "SABANALARGA"},
    "BOGOTA": {"BOGOTA D.C.", "BOGOTA DC", "BOGOTA D C", "BOGOTA"},
    "BOLIVAR": {"CARTAGENA", "TURBACO", "ARJONA", "EL CARMEN DE BOLIVAR"},
    "BOYACA": {"TUNJA", "SOGAMOSO", "CHIQUINQUIRA", "DUITAMA", "PUERTO BOYACA"},
    "CALDAS": {
        "MANIZALES", "RIOSUCIO", "LA DORADA", "PENSILVANIA",
        "SALAMINA", "ANSERMA",
    },
    "CAQUETA": {"FLORENCIA"},
    "CASANARE": {
        "YOPAL", "VILLANUEVA", "AGUAZUL", "PAZ DE ARIPORO",
        "TAURAMENA", "MONTERREY", "TRINIDAD", "PORE", "MANI",
        "HATO COROZAL",
    },
    "CAUCA": {"POPAYAN", "EL TAMBO"},
    "CESAR": {"VALLEDUPAR", "AGUACHICA", "LA PAZ", "AGUSTIN CODAZZI"},
    "CHOCO": {"QUIBDO"},
    "CORDOBA": {"MONTERIA", "CERETE", "CHINU"},
    "CUNDINAMARCA": {
        "SOACHA", "GIRARDOT", "CHIA", "FUSAGASUGA", "MOSQUERA",
        "CAJICA", "FACATATIVA", "ZIPAQUIRA", "FUNZA", "MADRID",
        "LA MESA",
    },
    "EXTERIOR": {"ESTADOS UNIDOS"},
    "HUILA": {"NEIVA", "PITALITO", "GARZON", "LA PLATA"},
    "LA GUAJIRA": {"RIOHACHA", "MAICAO", "MANAURE", "SAN JUAN DEL CESAR"},
    "MAGDALENA": {
        "SANTA MARTA", "EL BANCO", "CIENAGA", "ZONA BANANERA",
        "FUNDACION", "ARACATACA", "PLATO", "PIVIJAY", "PUEBLOVIEJO",
    },
    "META": {"VILLAVICENCIO", "ACACIAS", "GRANADA", "GUAMAL", "PUERTO GAITAN", "PUERTO LOPEZ"},
    "NARINO": {"PASTO", "TUMACO"},
    "NORTE DE SANTANDER": {
        "CUCUTA", "OCANA", "VILLA DEL ROSARIO", "LOS PATIOS", "PAMPLONA",
    },
    "PUTUMAYO": {"MOCOA"},
    "QUINDIO": {"ARMENIA", "CALARCA"},
    "RISARALDA": {"PEREIRA", "DOSQUEBRADAS", "SANTA ROSA DE CABAL"},
    "SAN ANDRES": {"SAN ANDRES"},
    "SANTANDER": {
        "BUCARAMANGA", "FLORIDABLANCA", "PIEDECUESTA", "BARRANCABERMEJA",
        "BARBOSA", "SAN GIL", "SAN VICENTE DE CHUCURI", "SOCORRO",
        "CIMITARRA",
    },
    "SUCRE": {
        "SINCELEJO", "SUCRE", "MAJAGUAL", "SAN MARCOS", "SAN PEDRO",
        "SINCE", "COVENAS", "COROZAL", "SAN BENITO ABAD", "TOLU",
    },
    "TOLIMA": {"IBAGUE", "ESPINAL", "MARIQUITA"},
    "VALLE DEL CAUCA": {
        "CALI", "PALMIRA", "TULUA", "BUGA", "CARTAGO",
        "BUENAVENTURA", "JAMUNDI", "LA UNION", "BOLIVAR",
    },
    "VICHADA": {"PUERTO CARRENO"},
}

# Flat set for quick lookup: "DEPT|MUNI"
_MUNICIPIOS_OBJETIVO_FLAT: set = set()
for _dept, _munis in MUNICIPIOS_OBJETIVO.items():
    for _muni in _munis:
        _MUNICIPIOS_OBJETIVO_FLAT.add(f"{_dept}|{_muni}")


# ── PMSN Business Rules ─────────────────────────────────────────────
# Procuraduría / Ministerio Público — Reglas específicas de auditoría
PMSN_CAMARA_SENADO_DIFF_PCT = 0.10   # 10% diferencia Cámara vs Senado
PMSN_PARTIDOS_TACHON = [              # Partidos bajo vigilancia de tachones
    "CENTRO DEMOCRATICO",
    "PACTO HISTORICO",
]
PMSN_MIN_FIRMAS = 3                   # Mínimo de firmas requeridas en E-14
PMSN_NULO_PCT_THRESHOLD = 0.06        # 6% voto nulo = alerta
PMSN_SENADO_MIN_VOTES_PARETO = 2      # 0 o 1 votos = sospechoso en paretos

# ── PMSN Risk Types ──────────────────────────────────────────────────
PMSN_RISK_ALTO = "R_ALTO"       # Rojo
PMSN_RISK_MEDIO = "R_MEDIO"     # Naranja
PMSN_RISK_BAJO = "R_BAJO"       # Amarillo

# ── PMSN Graduated thresholds ────────────────────────────────────────
PMSN_03_DIFF_ALTO  = 20    # |diff| > 20 votos → R_ALTO
PMSN_03_DIFF_MEDIO =  5    # |diff| 6-20       → R_MEDIO  (≤5 → R_BAJO)

PMSN_04_DIFF_ALTO  = 15    # |diff| > 15 → R_ALTO
PMSN_04_DIFF_MEDIO =  3    # |diff| 4-15 → R_MEDIO  (1-3 → R_BAJO)

PMSN_07_NULO_ALTO  = 0.30  # > 30% → R_ALTO
PMSN_07_NULO_MEDIO = 0.15  # 15-30% → R_MEDIO  (6-15% → R_BAJO)


# ── Shared utilities ─────────────────────────────────────────────────

def _safe_int(value: Any) -> int:
    """Convert value to int, treating None as 0 for arithmetic."""
    if value is None:
        return 0
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def compute_party_sum(partidos: List[Dict[str, Any]]) -> int:
    """Sum all party votes from a partidos list."""
    return sum(_safe_int(p.get("votes")) for p in partidos)


def compute_full_sum(
    partidos: List[Dict[str, Any]],
    blancos: int,
    nulos: int,
    no_marcados: int = 0,
) -> int:
    """Compute total: parties + blancos + nulos + no_marcados."""
    return compute_party_sum(partidos) + (blancos or 0) + (nulos or 0) + (no_marcados or 0)


def classify_ocr_risk(confidence: float) -> str:
    """Classify a form by OCR confidence into risk level.

    Returns: 'high', 'medium', or 'low'.
    """
    if confidence < OCR_HIGH_RISK_THRESHOLD:
        return "high"
    if confidence < OCR_MEDIUM_RISK_THRESHOLD:
        return "medium"
    return "low"


def safe_percentage(value: int, total: int, decimals: int = 1) -> float:
    """Calculate percentage safely, return 0.0 if total is 0."""
    if total <= 0:
        return 0.0
    return round(value / total * 100, decimals)


def is_municipio_objetivo(departamento: str, municipio: str) -> bool:
    """Check if a dept+muni pair is in the target scope.

    Compares normalized (uppercase, no accents) names against
    MUNICIPIOS_OBJETIVO. Resolves dept aliases (e.g. VALLE → VALLE DEL CAUCA)
    before matching, then falls back to substring match for OCR noise.
    """
    if not departamento or not municipio:
        return False
    dept = _DEPT_ALIASES.get(departamento.upper().strip(), departamento.upper().strip())
    muni = municipio.upper().strip()

    # Exact match
    if f"{dept}|{muni}" in _MUNICIPIOS_OBJETIVO_FLAT:
        return True

    # Fuzzy: check if any target muni is contained in the OCR muni or vice-versa
    target_munis = MUNICIPIOS_OBJETIVO.get(dept)
    if not target_munis:
        return False
    for target in target_munis:
        if target in muni or muni in target:
            return True
    return False
