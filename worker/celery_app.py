from celery import Celery

from app.core.config import settings

celery = Celery(
    "mlr_ruleops",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery.conf.update(task_serializer="json", accept_content=["json"], result_serializer="json", timezone="UTC")


@celery.task(name="process_ticket")
def process_ticket_task(ticket_id: str) -> str:
    from app.db.session import SessionLocal
    from app.workflow.orchestrator import TicketOrchestrator

    db = SessionLocal()
    try:
        TicketOrchestrator(db).process(ticket_id, actor_id="worker")
        db.commit()
        return ticket_id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
