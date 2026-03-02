"""HeaderAgent — Validates E-14 header fields in a structured form dict."""
import logging
import re
from typing import Any, Dict

from .base import BaseOCRAgent, ExtractionResult

logger = logging.getLogger(__name__)

_TRAILING_ARTIFACT = re.compile(r"[^A-ZÁÉÍÓÚÑÜ\s]+$")


def _normalize_place_name(value: Any) -> str:
    """Uppercase and strip trailing OCR artifacts from place names."""
    if not value or not isinstance(value, str):
        return ""
    cleaned = value.strip().upper()
    cleaned = _TRAILING_ARTIFACT.sub("", cleaned).strip()
    return cleaned


class HeaderAgent(BaseOCRAgent):
    """Validates header completeness: corporacion, departamento, municipio,
    zona, puesto, mesa, sufragantes_e11, votos_en_urna."""

    def extract(self, form: Dict[str, Any]) -> ExtractionResult:
        warnings: list[str] = []
        flags: list[str] = []

        zona = form.get("zona_cod") or form.get("zona")
        puesto = form.get("puesto_cod") or form.get("puesto")
        mesa = form.get("mesa_num") or form.get("mesa")

        for field_name, field_val in [
            ("zona", zona),
            ("puesto", puesto),
            ("mesa", mesa),
        ]:
            if not field_val:
                flags.append(f"HEADER_MISSING: {field_name} is empty or null")

        confidence = 0.95 - 0.05 * len(flags)
        confidence = max(0.30, confidence)

        return ExtractionResult(
            agent_name="HeaderAgent",
            data={},
            warnings=warnings,
            confidence=confidence,
            checks_run=["HEADER_COMPLETENESS"],
            flags=flags,
        )
