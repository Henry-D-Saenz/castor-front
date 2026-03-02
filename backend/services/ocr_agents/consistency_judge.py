"""ConsistencyJudge — Merges agent flags and runs validate_form."""
import logging
from typing import Any, Dict, List

from .base import ExtractionResult
from ..e14_validator import validate_form

logger = logging.getLogger(__name__)


class ConsistencyJudge:
    """Merges outputs from the three agents, runs validate_form,
    and returns a validation dict compatible with the store schema."""

    def judge(
        self,
        header_result: ExtractionResult,
        totals_result: ExtractionResult,
        parties_result: ExtractionResult,
        form: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Run validate_form on the (already agent-corrected) form.

        Args:
            header_result: Output from HeaderAgent.
            totals_result: Output from TotalsAgent.
            parties_result: Output from PartiesAgent.
            form: The structured form dict (may have been modified in-place
                  by PartiesAgent corrections).

        Returns:
            Validation dict matching the schema expected by e14_json_store.
        """
        validation = validate_form(form, auto_correct=True)

        # Append agent flags as extra diagnoses so they're visible
        extra_flags = (
            header_result.flags + totals_result.flags + parties_result.flags
        )
        if extra_flags:
            existing_diagnoses: List[str] = validation.get("diagnoses", [])
            validation["diagnoses"] = existing_diagnoses + extra_flags

        # Collect agent warnings
        all_warnings = (
            header_result.warnings
            + totals_result.warnings
            + parties_result.warnings
        )
        if all_warnings:
            validation["agent_warnings"] = all_warnings

        # Composite confidence: lower of agent min and validator confidence
        agent_min = min(
            header_result.confidence,
            totals_result.confidence,
            parties_result.confidence,
        )
        val_conf = validation.get("validation_confidence", 1.0)
        validation["validation_confidence"] = round(
            min(agent_min, val_conf), 4
        )

        return validation
