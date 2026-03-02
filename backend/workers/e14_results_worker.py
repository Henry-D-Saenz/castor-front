"""Background worker: process pending document_ids from Azure SQL queue."""
from __future__ import annotations

import logging
import time

from config import Config
from services.e14_results_fetcher import fetch_normalized_form
from services.e14_sql_queue import claim_pending_batch, mark_failed, mark_synced

logger = logging.getLogger(__name__)


def run_forever() -> None:
    if not Config.E14_SQL_QUEUE_ENABLED:
        raise RuntimeError("E14_SQL_QUEUE_ENABLED must be true to run this worker")

    batch_size = int(getattr(Config, "E14_SQL_WORKER_BATCH_SIZE", 200) or 200)
    poll_seconds = int(getattr(Config, "E14_SQL_WORKER_POLL_SECONDS", 5) or 5)
    logger.info(
        "E14 worker starting: batch_size=%d poll_seconds=%d",
        batch_size,
        poll_seconds,
    )
    while True:
        try:
            document_ids = claim_pending_batch(batch_size)
        except Exception as exc:
            logger.error("Worker failed claiming batch: %s", exc, exc_info=True)
            time.sleep(poll_seconds)
            continue

        if not document_ids:
            time.sleep(poll_seconds)
            continue

        logger.info("Worker claimed %d documents", len(document_ids))
        for document_id in document_ids:
            try:
                form = fetch_normalized_form(document_id)
                mark_synced(document_id, form)
            except Exception as exc:
                logger.error("Worker failed for %s: %s", document_id, exc)
                mark_failed(document_id, str(exc), retry_delay_seconds=300)


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    run_forever()

