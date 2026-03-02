"""E-14 in-memory cache service for the solo-front profile."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CACHE_TTL = int(os.environ.get('E14_CACHE_TTL', 3600))
CACHE_PREFIX = 'e14:'
PARTY_SUMMARY_KEY = f'{CACHE_PREFIX}party_summary'
TOTALS_KEY = f'{CACHE_PREFIX}totals'
FORMS_KEY = f'{CACHE_PREFIX}forms'


class E14CacheService:
    """Thread-safe memory cache with TTL."""

    def __init__(self, ttl: int = CACHE_TTL):
        self.ttl = ttl
        self._store: Dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        return True

    def _get_json(self, key: str):
        now = time.time()
        with self._lock:
            item = self._store.get(key)
            if not item:
                return None
            ts, payload = item
            if now - ts > self.ttl:
                self._store.pop(key, None)
                return None
            return json.loads(payload)

    def _set_json(self, key: str, value) -> bool:
        with self._lock:
            self._store[key] = (time.time(), json.dumps(value, ensure_ascii=False))
        return True

    def get_party_summary(self):
        return self._get_json(PARTY_SUMMARY_KEY)

    def set_party_summary(self, summary: list) -> bool:
        return self._set_json(PARTY_SUMMARY_KEY, summary)

    def get_totals(self) -> Optional[Dict[str, Any]]:
        return self._get_json(TOTALS_KEY)

    def set_totals(self, totals: Dict[str, Any]) -> bool:
        return self._set_json(TOTALS_KEY, totals)

    def get_forms(self, limit: int = 50) -> Optional[list]:
        return self._get_json(f"{FORMS_KEY}:{limit}")

    def set_forms(self, forms: list, limit: int = 50) -> bool:
        return self._set_json(f"{FORMS_KEY}:{limit}", forms)

    def get_full_response(self, limit: int = 50) -> Optional[Dict[str, Any]]:
        return self._get_json(f"{CACHE_PREFIX}response:{limit}")

    def set_full_response(self, response: Dict[str, Any], limit: int = 50) -> bool:
        response = dict(response)
        response['_cache'] = {
            'cached_at': datetime.utcnow().isoformat(),
            'ttl_seconds': self.ttl,
            'source': 'memory'
        }
        return self._set_json(f"{CACHE_PREFIX}response:{limit}", response)

    def clear_all(self) -> int:
        with self._lock:
            keys = list(self._store.keys())
            deleted = len([k for k in keys if k.startswith(CACHE_PREFIX)])
            self._store = {k: v for k, v in self._store.items() if not k.startswith(CACHE_PREFIX)}
            return deleted

    def clear_forms(self) -> int:
        with self._lock:
            keys = list(self._store.keys())
            patterns = (f"{FORMS_KEY}:", f"{CACHE_PREFIX}response:")
            deleted_keys = [k for k in keys if k.startswith(patterns)]
            for k in deleted_keys:
                self._store.pop(k, None)
            return len(deleted_keys)

    def get_cache_info(self) -> Dict[str, Any]:
        with self._lock:
            keys = [k for k in self._store.keys() if k.startswith(CACHE_PREFIX)]
        return {
            'available': True,
            'backend': 'memory',
            'ttl_seconds': self.ttl,
            'keys': len(keys),
            'prefix': CACHE_PREFIX,
        }


_cache_service: Optional[E14CacheService] = None
_cache_lock = threading.Lock()


def get_e14_cache_service() -> E14CacheService:
    global _cache_service
    if _cache_service is None:
        with _cache_lock:
            if _cache_service is None:
                _cache_service = E14CacheService()
    return _cache_service
