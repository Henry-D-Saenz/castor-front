"""Minimal E-14 data service used by solo-front routes."""
from __future__ import annotations

from typing import Any, Dict

from services.e14_json_store import get_e14_json_store


class E14DataService:
    """Small facade to fetch dashboard stats from the JSON store."""

    def __init__(self) -> None:
        self._store = get_e14_json_store()

    def get_stats(self) -> Dict[str, Any]:
        return self._store.get_stats()
