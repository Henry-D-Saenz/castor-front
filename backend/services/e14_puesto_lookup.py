"""
Lookup de nombres de puestos de votación.

Construye un índice en memoria desde lista_puestos_congreso_2022.json.
Clave: (municipio_normalizado, zona_cod_2dig, puesto_cod_2dig) → nombre del puesto.
"""
import json
import logging
import os
import threading
import unicodedata
from typing import Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_lookup: Optional[dict] = None

_DATA_FILE = os.path.join(
    os.path.dirname(__file__),  # backend/services/
    "..", "..",                  # project root
    "data", "actas_e14_masivo", "lista_puestos_congreso_2022.json",
)


def _norm(s: str) -> str:
    """Normalize: strip accents, uppercase, remove extra whitespace."""
    return (
        unicodedata.normalize("NFD", str(s))
        .encode("ascii", "ignore")
        .decode("ascii")
        .upper()
        .strip()
    )


def _build_lookup() -> dict:
    path = os.path.abspath(_DATA_FILE)
    if not os.path.exists(path):
        logger.warning("lista_puestos not found at %s — puesto lookup disabled", path)
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lookup: dict = {}
    for item in data:
        # muni field: "001 - MEDELLIN" → "MEDELLIN"
        muni_raw = item.get("municipio", "")
        muni_clean = _norm(muni_raw.split(" - ", 1)[-1] if " - " in muni_raw else muni_raw)

        # zona field: "ZONA 01" or "1" → "01"
        zona_raw = str(item.get("zona_cod") or item.get("zona") or "")
        zona_clean = zona_raw.replace("ZONA", "").strip().zfill(2)

        puesto_cod = str(item.get("puesto_cod", "")).zfill(2)
        puesto_name = item.get("puesto", "")

        if muni_clean and zona_clean and puesto_cod:
            key = (muni_clean, zona_clean, puesto_cod)
            # Prefer first (SENADO) entry; don't overwrite
            if key not in lookup:
                lookup[key] = puesto_name

    logger.info("Puesto lookup built: %d entries from %s", len(lookup), path)
    return lookup


def _get_lookup() -> dict:
    global _lookup
    if _lookup is None:
        with _lock:
            if _lookup is None:
                _lookup = _build_lookup()
    return _lookup


def get_puesto_nombre(municipio: str, zona_cod: str, puesto_cod: str) -> Optional[str]:
    """
    Return the full puesto name for a given municipio/zona/puesto combination.

    Strips the leading "NN - " prefix so only the school/place name is returned.
    Returns None if no match is found.
    """
    lookup = _get_lookup()
    if not lookup:
        return None

    key = (_norm(municipio), str(zona_cod).zfill(2), str(puesto_cod).zfill(2))
    nombre = lookup.get(key)
    if not nombre:
        return None

    # Strip "01 - " prefix to return clean name
    if " - " in nombre:
        nombre = nombre.split(" - ", 1)[1].strip()
    return nombre or None
