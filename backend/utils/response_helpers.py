"""
Response helpers for standardized API responses.
Provides thread-safe service initialization utilities.
"""
from threading import Lock
from typing import Any, Dict, Optional, Callable


# =============================================================================
# THREAD-SAFE SERVICE INITIALIZATION
# =============================================================================

class ThreadSafeServiceFactory:
    """
    Thread-safe lazy initialization of services.
    Uses double-checked locking pattern.
    """

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._locks: Dict[str, Lock] = {}
        self._global_lock = Lock()

    def get_or_create(self, name: str, factory: Callable[[], Any]) -> Any:
        """
        Get existing service or create new one thread-safely.

        Args:
            name: Service identifier
            factory: Callable that creates the service

        Returns:
            The service instance
        """
        # Fast path - service already exists
        if name in self._services:
            return self._services[name]

        # Slow path - need to potentially create service
        with self._global_lock:
            # Get or create lock for this service
            if name not in self._locks:
                self._locks[name] = Lock()

        with self._locks[name]:
            # Double-check after acquiring lock
            if name not in self._services:
                self._services[name] = factory()
            return self._services[name]

    def clear(self, name: Optional[str] = None):
        """Clear service(s) from cache."""
        with self._global_lock:
            if name:
                self._services.pop(name, None)
            else:
                self._services.clear()


# Global service factory instance
service_factory = ThreadSafeServiceFactory()
