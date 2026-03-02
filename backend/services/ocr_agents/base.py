"""Base classes for OCR validation agents."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result returned by each OCR agent after extraction and validation."""

    agent_name: str
    data: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    confidence: float = 0.95
    checks_run: List[str] = field(default_factory=list)
    flags: List[str] = field(default_factory=list)


class BaseOCRAgent(ABC):
    """Abstract base class for domain-specific OCR validation agents.

    Each agent receives the already-structured form dict and validates
    its own domain without making any external API calls.
    """

    @abstractmethod
    def extract(self, form: Dict[str, Any]) -> ExtractionResult:
        """Validate domain-specific fields from a structured form dict.

        Args:
            form: Structured form dict already parsed by Azure OCR.

        Returns:
            ExtractionResult with flags and warnings for this domain.
        """
        ...


from ..e14_constants import _safe_int  # noqa: F401 — re-exported for agents
