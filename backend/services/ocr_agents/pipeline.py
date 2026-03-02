"""Pipeline — runs validation agents over an already-structured E-14 form dict."""
import logging
from typing import Any, Dict

from .header_agent import HeaderAgent
from .totals_agent import TotalsAgent
from .parties_agent import PartiesAgent
from .consistency_judge import ConsistencyJudge

logger = logging.getLogger(__name__)

_header_agent = HeaderAgent()
_totals_agent = TotalsAgent()
_parties_agent = PartiesAgent()
_judge = ConsistencyJudge()


def run_validation_pipeline(form: Dict[str, Any]) -> Dict[str, Any]:
    """Run HeaderAgent + TotalsAgent + PartiesAgent + ConsistencyJudge.

    Agents may modify `form` in-place (dedup, code-as-votes corrections).
    Returns a validation dict compatible with form["validation"] schema.

    Args:
        form: Structured form dict already parsed by Azure OCR.

    Returns:
        Validation dict with keys: is_valid, checks, diagnoses,
        auto_corrected, corrections_applied, needs_human_review,
        review_priority, validation_confidence, null_fields, agent_warnings.
    """
    mesa_id = form.get("mesa_id", "?")
    logger.debug("Validation pipeline: mesa_id=%s", mesa_id)

    header_result = _header_agent.extract(form)
    totals_result = _totals_agent.extract(form)
    parties_result = _parties_agent.extract(form)

    if header_result.flags or totals_result.flags or parties_result.flags:
        logger.debug(
            "Agent flags for mesa %s: header=%d totals=%d parties=%d",
            mesa_id,
            len(header_result.flags),
            len(totals_result.flags),
            len(parties_result.flags),
        )

    return _judge.judge(header_result, totals_result, parties_result, form)
