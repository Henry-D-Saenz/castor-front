"""
E14 OCR Normalization — fuzzy matching and cleanup for department,
municipality, and polling station names extracted via Tesseract OCR.
"""
import logging
import re
import unicodedata
from difflib import get_close_matches
from typing import Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical catalogs
# ---------------------------------------------------------------------------

CANONICAL_DEPARTMENTS = [
    "AMAZONAS", "ANTIOQUIA", "ARAUCA", "ATLANTICO", "BOGOTA",
    "BOLIVAR", "BOYACA", "CALDAS", "CAQUETA", "CASANARE",
    "CAUCA", "CESAR", "CHOCO", "CORDOBA", "CUNDINAMARCA",
    "GUAINIA", "GUAVIARE", "HUILA", "LA GUAJIRA", "MAGDALENA",
    "META", "NARINO", "NORTE DE SANTANDER", "PUTUMAYO",
    "QUINDIO", "RISARALDA", "SAN ANDRES", "SANTANDER",
    "SUCRE", "TOLIMA", "VALLE DEL CAUCA", "VAUPES", "VICHADA",
]

CANONICAL_MUNICIPALITIES: Dict[str, List[str]] = {
    "ANTIOQUIA": [
        "MEDELLIN", "BELLO", "ITAGUI", "ENVIGADO", "APARTADO",
        "TURBO", "RIONEGRO", "CAUCASIA", "COPACABANA", "SABANETA",
        "LA ESTRELLA", "CALDAS", "BARBOSA", "GIRARDOTA", "MARINILLA",
    ],
}

CANONICAL_PUESTOS: Dict[str, List[str]] = {
    "MEDELLIN": [
        "INST.EDUC. LA CANDELARIA",
        "SEC.ESC. MANUEL URIBE ANGEL",
        "SEC. ESC. DIVINA PROVIDENCIA",
        "I.E. ASIA IGNACIANA",
        "SEC. ESC. MEDELLIN",
        "SEC. ESC. LA ESPERANZA NO 2",
        "SEC.ESC.AGRIPINA MONTES DEL VALLE",
        "IE.MARIA DE LOS ANGELES CANO MARQUEZ",
        "I.E.GUADALUPE",
        "IE ANTONIO DERKA",
        "I.E.FEDERICO CARRASQUILLA",
        "I.E.FE Y ALEGRIA GRANIZAL",
        "IE LA AVANZADA",
        "SEC. ESC. CARPINELO AMAPOLITA",
    ],
}

# DANE department codes (fallback for empty OCR fields)
DANE_DEPT = {
    "01": "ANTIOQUIA", "02": "ATLANTICO", "03": "BOGOTA",
    "04": "BOLIVAR", "05": "BOYACA", "06": "CALDAS",
    "07": "CAQUETA", "08": "CAUCA", "09": "CESAR",
    "10": "CORDOBA", "11": "CUNDINAMARCA", "12": "CHOCO",
    "13": "HUILA", "14": "LA GUAJIRA", "15": "MAGDALENA",
    "16": "META", "17": "NARINO", "18": "NORTE DE SANTANDER",
    "19": "QUINDIO", "20": "RISARALDA", "21": "SANTANDER",
    "22": "SUCRE", "23": "TOLIMA", "24": "VALLE DEL CAUCA",
    "25": "ARAUCA", "26": "CASANARE", "27": "PUTUMAYO",
    "28": "SAN ANDRES", "29": "AMAZONAS", "30": "GUAINIA",
    "31": "GUAVIARE", "32": "VAUPES", "33": "VICHADA",
}

DANE_MUNI: Dict[str, Dict[str, str]] = {
    "01": {"001": "MEDELLIN", "002": "ABEJORRAL", "003": "ABRIAQUI"},
}

# ---------------------------------------------------------------------------
# Normalization functions
# ---------------------------------------------------------------------------


def normalize_name(value: str) -> str:
    """Strip OCR noise from department/municipality names."""
    if not value:
        return ""
    text = value.upper().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^A-Z\s]", "", text).strip()
    text = re.sub(r"\s+[A-Z]{1,2}$", "", text)
    return text


def normalize_puesto(value: str) -> str:
    """Clean OCR noise from polling station names.

    OCR commonly misreads 'I' as |, ¡, 1, l, [, (, J at the start of
    institution names (I.E., IE, INST).
    """
    if not value:
        return ""
    text = value.strip()

    # 1) Remove trailing OCR artifacts
    text = re.sub(r'[\s]*[|¡)\](\[.:!\'\"]+\s*$', '', text)
    text = re.sub(r'\s+[A-Za-z0-9]{1}\s*$', '', text)

    # 2) Normalize accents early
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")

    # 3) Replace OCR misreads of "I" before ".E" or "E "
    text = re.sub(r'^[\[\]()|¡1lJ],?\s*(?=[.,]?E[.,\s])', 'I', text)

    # 4) Fix embedded OCR noise: I¡GNACIANA → IGNACIANA
    text = re.sub(r'[|¡\]\[)(]', '', text)

    # 5) Remove leading brackets/parens that survived
    text = re.sub(r'^[\[\]()+]+', '', text)

    # 6) Normalize punctuation
    text = re.sub(r'(?<=\w),(?=\s)', '.', text)
    text = re.sub(r'(?<=\w),(?=\w)', '.', text)
    text = re.sub(r'INST\.EDUC\.,', 'INST.EDUC.', text)

    # 7) Collapse double spaces
    text = re.sub(r'\s{2,}', ' ', text).strip()
    return text


def fuzzy_match(name: str, candidates: List[str], cutoff: float = 0.7) -> str:
    """Return closest canonical match for an OCR-noisy name, or original."""
    if not name or name in candidates:
        return name
    matches = get_close_matches(name, candidates, n=1, cutoff=cutoff)
    if matches:
        logger.debug("Fuzzy matched '%s' -> '%s'", name, matches[0])
        return matches[0]
    return name


def infer_from_filename(filename: str, dept: str, muni: str) -> tuple:
    """Infer empty dept/muni from DANE codes in the filename."""
    stem = filename.replace(".pdf", "").replace("_tesseract.json", "")
    parts = stem.split("_")
    if len(parts) < 10:
        return dept, muni
    dept_code, muni_code = parts[4], parts[5]
    if not dept:
        dept = DANE_DEPT.get(dept_code, "")
    if not muni and dept_code in DANE_MUNI:
        muni = DANE_MUNI[dept_code].get(muni_code, "")
    return dept, muni
