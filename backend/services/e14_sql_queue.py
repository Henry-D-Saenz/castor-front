"""Azure SQL queue/cache access for high-volume E14 flows."""
from __future__ import annotations

import hashlib
import json
from typing import List

from config import Config

try:
    import pyodbc  # type: ignore
except Exception:  # pragma: no cover
    pyodbc = None


class E14SqlQueueError(RuntimeError):
    pass


def _require_ready() -> None:
    if not Config.E14_SQL_QUEUE_ENABLED:
        raise E14SqlQueueError("E14_SQL_QUEUE_ENABLED is false")
    if not Config.E14_SQL_CONNECTION_STRING:
        raise E14SqlQueueError("E14_SQL_CONNECTION_STRING is empty")
    if pyodbc is None:
        raise E14SqlQueueError("pyodbc is not installed")


def _connect():
    _require_ready()
    return pyodbc.connect(Config.E14_SQL_CONNECTION_STRING, timeout=30)


def enqueue_document(document_id: str, source: str = "webhook") -> None:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("EXEC dbo.usp_e14_enqueue_document ?, ?", document_id, source)
        conn.commit()


def claim_pending_batch(batch_size: int) -> List[str]:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("EXEC dbo.usp_e14_claim_pending_batch ?", int(batch_size))
        rows = cur.fetchall()
        conn.commit()
    return [str(r[0]).strip() for r in rows if str(r[0]).strip()]


def mark_synced(document_id: str, normalized_form: dict) -> None:
    payload_json = json.dumps(normalized_form, ensure_ascii=False)
    payload_hash = hashlib.sha256(payload_json.encode("utf-8")).digest()
    processed_at = normalized_form.get("processed_at")
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            EXEC dbo.usp_e14_mark_synced
              @document_id=?,
              @filename=?,
              @corporacion=?,
              @departamento=?,
              @municipio=?,
              @mesa_id=?,
              @zona_cod=?,
              @puesto_cod=?,
              @mesa_num=?,
              @ocr_confidence=?,
              @total_votos=?,
              @processed_at=?,
              @result_json=?,
              @result_hash=?
            """,
            document_id,
            normalized_form.get("filename"),
            normalized_form.get("corporacion"),
            normalized_form.get("departamento"),
            normalized_form.get("municipio"),
            normalized_form.get("mesa_id"),
            normalized_form.get("zona"),
            normalized_form.get("puesto"),
            normalized_form.get("mesa"),
            normalized_form.get("confidence"),
            normalized_form.get("total_votos"),
            processed_at,
            payload_json,
            payload_hash,
        )
        conn.commit()


def mark_failed(document_id: str, error: str, retry_delay_seconds: int = 300) -> None:
    safe_error = (error or "")[:3900]
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "EXEC dbo.usp_e14_mark_failed ?, ?, ?",
            document_id,
            safe_error,
            int(retry_delay_seconds),
        )
        conn.commit()

