"""
Caching utilities for CASTOR ELECCIONES.
Memory-only cache backend with TTL helper.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Dict, Optional, Tuple

from config import Config

logger = logging.getLogger(__name__)


class TTLCache:
    """Thread-safe TTL cache with optional per-entry TTL and stale window."""

    def __init__(
        self,
        ttl_seconds: int = 300,
        max_size: int = 128,
        stale_ttl_seconds: int = 0,
    ):
        self.default_ttl = ttl_seconds
        self.max_size = max_size
        self.stale_ttl = stale_ttl_seconds
        self._data: "OrderedDict[Any, Tuple[Any, float, float]]" = OrderedDict()
        self._lock = threading.Lock()

    def _evict_if_needed(self) -> None:
        while len(self._data) > self.max_size:
            self._data.popitem(last=False)

    def set(self, key: Any, value: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds or self.default_ttl
        with self._lock:
            self._data[key] = (value, time.time(), ttl)
            self._data.move_to_end(key)
            self._evict_if_needed()

    def get(self, key: Any) -> Optional[Any]:
        value, is_stale = self.get_with_meta(key)
        if value is None or is_stale:
            return None
        return value

    def get_with_meta(self, key: Any) -> Tuple[Optional[Any], bool]:
        """
        Returns (value, is_stale). Removes expired entries automatically.
        """
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None, False
            value, timestamp, ttl = entry
            age = time.time() - timestamp
            if age < ttl:
                self._data.move_to_end(key)
                return value, False
            if self.stale_ttl and age < ttl + self.stale_ttl:
                self._data.move_to_end(key)
                return value, True
            self._data.pop(key, None)
            return None, False

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


class BackgroundTaskRunner:
    """Thin wrapper around ThreadPoolExecutor."""

    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, fn, *args, **kwargs) -> Future:
        return self._executor.submit(fn, *args, **kwargs)


background_tasks = BackgroundTaskRunner()

# Local cache fallback for shared operations
_local_cache = TTLCache(
    ttl_seconds=Config.CACHE_TTL_TWITTER,
    max_size=Config.CACHE_MAX_SIZE * 4,
    stale_ttl_seconds=60,
)


def init_cache() -> None:
    """Initialize cache backend (memory-only in solo-front profile)."""
    logger.info("Using in-memory cache backend")


def _serialize(value: Any) -> str:
    return json.dumps(value, default=str)


def _deserialize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return json.loads(value)


def get_cache_key(prefix: str, *args, **kwargs) -> str:
    """Build deterministic cache key from args/kwargs."""
    serialized_args = ":".join(str(arg) for arg in args)
    serialized_kwargs = ":".join(f"{k}={kwargs[k]}" for k in sorted(kwargs))
    raw_key = f"{prefix}:{serialized_args}:{serialized_kwargs}"
    hashed = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return f"castor:{prefix}:{hashed}"


def set(key: str, value: Any, ttl: int) -> None:
    """Store value in cache."""
    payload = _serialize(value)
    _local_cache.set(key, payload, ttl_seconds=ttl)


def get(key: str) -> Any:
    """Get cached value."""
    cached, _ = _local_cache.get_with_meta(key)
    if cached is None:
        return None
    return _deserialize(cached)


def get_with_info(key: str) -> tuple:
    """
    Get cached value with cache info.

    Returns:
        tuple: (value, from_cache, cached_at_timestamp)
        - value: The cached value or None
        - from_cache: True if value came from cache
        - cached_at_timestamp: Unix timestamp when cached, or None
    """
    with _local_cache._lock:
        entry = _local_cache._data.get(key)
        if not entry:
            return None, False, None
        value, timestamp, ttl = entry
        age = time.time() - timestamp
        if age < ttl:
            _local_cache._data.move_to_end(key)
            return _deserialize(value), True, timestamp
        if _local_cache.stale_ttl and age < ttl + _local_cache.stale_ttl:
            _local_cache._data.move_to_end(key)
            return _deserialize(value), True, timestamp
        _local_cache._data.pop(key, None)
        return None, False, None


def cached(prefix: str, ttl: int = 60) -> Callable:
    """Decorator to cache function results."""

    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            cache_key = get_cache_key(prefix, *args, **kwargs)
            cached_value = get(cache_key)
            if cached_value is not None:
                return cached_value
            result = func(*args, **kwargs)
            set(cache_key, result, ttl)
            return result

        return wrapper

    return decorator


def invalidate(key_pattern: str) -> int:
    """
    Invalidate cache entries matching pattern.

    Args:
        key_pattern: Pattern to match (e.g., 'castor:twitter:*')

    Returns:
        Number of keys deleted
    """
    # Local in-memory backend does not support pattern delete efficiently.
    return 0


def invalidate_prefix(prefix: str) -> int:
    """Invalidate all cache entries with given prefix."""
    return invalidate(f"castor:{prefix}:*")


def clear_all() -> None:
    """Clear all cache entries."""
    _local_cache.clear()
    logger.info("Local cache cleared")
