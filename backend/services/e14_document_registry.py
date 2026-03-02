"""Simple file-backed registry for OCR document_ids (no DB)."""
from __future__ import annotations

import os
import threading
from typing import List, Set


class E14DocumentRegistry:
    """Append-only registry of document IDs with in-memory dedup cache."""

    def __init__(self, filepath: str):
        self._filepath = filepath
        self._lock = threading.Lock()
        self._ids: Set[str] = set()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._ids = set()
            if os.path.isfile(self._filepath):
                try:
                    with open(self._filepath, "r", encoding="utf-8") as fh:
                        for line in fh:
                            doc_id = line.strip()
                            if doc_id:
                                self._ids.add(doc_id)
                except OSError:
                    self._ids = set()
            self._loaded = True

    def add_ids(self, document_ids: List[str]) -> int:
        """Append only IDs not already seen. Returns added count."""
        self._ensure_loaded()
        clean = [str(x).strip() for x in document_ids if str(x).strip()]
        if not clean:
            return 0
        with self._lock:
            # Deduplicate within the same batch and against already loaded IDs.
            to_add: List[str] = []
            seen_batch: Set[str] = set()
            for doc_id in clean:
                if doc_id in self._ids or doc_id in seen_batch:
                    continue
                seen_batch.add(doc_id)
                to_add.append(doc_id)
            if not to_add:
                return 0
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            with open(self._filepath, "a", encoding="utf-8") as fh:
                for doc_id in to_add:
                    fh.write(doc_id + "\n")
                    self._ids.add(doc_id)
        return len(to_add)

    def has(self, document_id: str) -> bool:
        self._ensure_loaded()
        return str(document_id or "").strip() in self._ids

    def list_ids(self) -> List[str]:
        self._ensure_loaded()
        return sorted(self._ids)

    def clear(self) -> None:
        self._ensure_loaded()
        with self._lock:
            self._ids = set()
            try:
                if os.path.isfile(self._filepath):
                    os.remove(self._filepath)
            except OSError:
                pass


_registry: E14DocumentRegistry | None = None
_registry_lock = threading.Lock()


def get_registry() -> E14DocumentRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                from config import Config
                path = os.path.join(Config.E14_DATA_DIR, "document_ids.log")
                _registry = E14DocumentRegistry(path)
    return _registry
