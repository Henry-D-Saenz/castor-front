"""TotalsAgent — Validates E-14 total vote fields in a structured form dict."""
import logging
from typing import Any, Dict, List

from .base import BaseOCRAgent, ExtractionResult

logger = logging.getLogger(__name__)


class TotalsAgent(BaseOCRAgent):
    """Validates presence of: total_votos, votos_blancos, votos_nulos."""

    def extract(self, form: Dict[str, Any]) -> ExtractionResult:
        warnings: List[str] = []
        flags: List[str] = []

        total_votos = form.get("total_votos")

        if total_votos is None:
            flags.append("TOTAL_MISSING: total_votos is null")

        confidence = 0.95 - 0.05 * len(flags)
        confidence = max(0.20, confidence)

        return ExtractionResult(
            agent_name="TotalsAgent",
            data={},
            warnings=warnings,
            confidence=confidence,
            checks_run=["TOTAL_PRESENT"],
            flags=flags,
        )
