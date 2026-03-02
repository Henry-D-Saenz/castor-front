"""PartiesAgent — Validates and auto-corrects E-14 party entries."""
import logging
import re
from typing import Any, Dict, List

from .base import BaseOCRAgent, ExtractionResult, _safe_int
from ..e14_constants import CODE_AS_VOTES_THRESHOLD

logger = logging.getLogger(__name__)

_PARTY_CODE_PATTERN = re.compile(r"^\d{4}$")


def _dedup_parties(partidos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate parties by party_code, keeping the first occurrence."""
    seen_codes: set[str] = set()
    unique: List[Dict[str, Any]] = []
    for p in partidos:
        code = p.get("party_code", "")
        if code and code in seen_codes:
            logger.debug("Dropping duplicate party_code=%s", code)
            continue
        if code:
            seen_codes.add(code)
        unique.append(p)
    return unique


def _detect_code_as_votes(
    partidos: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Detect if a party's vote count matches a 4-digit code pattern."""
    suspects: List[Dict[str, Any]] = []
    for i, p in enumerate(partidos):
        votes = _safe_int(p.get("votes"))
        if votes > CODE_AS_VOTES_THRESHOLD:
            if _PARTY_CODE_PATTERN.match(str(votes)):
                suspects.append({
                    "party_idx": i,
                    "party_name": p.get("party_name", ""),
                    "party_code": p.get("party_code", ""),
                    "suspicious_votes": votes,
                })
    return suspects


class PartiesAgent(BaseOCRAgent):
    """Validates the partidos list: dedup and code-as-votes detection.

    Auto-corrects suspected code-as-votes entries in-place (votes → 0).
    """

    def extract(self, form: Dict[str, Any]) -> ExtractionResult:
        warnings: List[str] = []
        flags: List[str] = []
        checks_run = ["DEDUP_PARTY_CODE", "CODE_AS_VOTES"]

        raw_partidos = form.get("partidos", [])

        partidos = _dedup_parties(raw_partidos)
        removed = len(raw_partidos) - len(partidos)
        if removed:
            warnings.append(f"Removed {removed} duplicate party entries")
            # Update form in-place so downstream sees deduplicated list
            form["partidos"] = partidos

        code_suspects = _detect_code_as_votes(partidos)
        for cs in code_suspects:
            flags.append(
                f"CODE_AS_VOTES: party '{cs['party_name']}' "
                f"(idx={cs['party_idx']}) votes={cs['suspicious_votes']} "
                "matches 4-digit code pattern — corrected to 0"
            )
            # Auto-correct in-place
            partidos[cs["party_idx"]]["votes"] = 0
            partidos[cs["party_idx"]]["needs_review"] = True

        confidence = 0.95 - 0.05 * len(flags)
        confidence = max(0.20, confidence)

        return ExtractionResult(
            agent_name="PartiesAgent",
            data={"code_as_votes_suspects": code_suspects},
            warnings=warnings,
            confidence=confidence,
            checks_run=checks_run,
            flags=flags,
        )
