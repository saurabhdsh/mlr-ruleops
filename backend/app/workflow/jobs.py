from __future__ import annotations

import os

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("workflow.jobs")


def enqueue_ticket_process(ticket_id: str, timeout: int = 240) -> bool:
    """Dispatch to Celery when a worker is actually listening. Returns True if the worker ran the job."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    try:
        from celery import Celery

        app = Celery("mlr_ruleops", broker=settings.redis_url, backend=settings.redis_url)
        ping = app.control.inspect(timeout=0.6).ping()
        if not ping:
            logger.info("no_celery_workers_inline_process")
            return False
        result = app.send_task("process_ticket", args=[ticket_id])
        result.get(timeout=timeout)
        logger.info("ticket_processed_by_worker", ticket_id=ticket_id, task_id=result.id)
        return True
    except Exception as exc:
        logger.info("worker_unavailable_inline_process", error=str(exc)[:240])
        return False
