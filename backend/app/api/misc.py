import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.api.deps import DbDep, UserDep
from app.core.config import settings
from app.integrations.registry import integration_status
from app.models.audit import AuditEvent, WorkflowEvent
from app.models.citation import ScientificCitation
from app.models.validation import TestResult, TestRun
from app.schemas.tickets import WebhookTicket
from app.services.analytics import dashboard_metrics
from app.services.ticket_service import create_ticket

router = APIRouter(tags=["platform"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@router.get("/ready")
def ready(db: DbDep) -> dict:
    db.execute(__import__("sqlalchemy").text("SELECT 1"))
    return {"status": "ready"}


@router.get("/analytics/dashboard")
def analytics(db: DbDep, user: UserDep) -> dict:
    return dashboard_metrics(db)


@router.get("/audit")
def audit_list(
    db: DbDep,
    user: UserDep,
    event_type: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[dict]:
    q = db.query(AuditEvent)
    if event_type:
        q = q.filter(AuditEvent.event_type == event_type)
    rows = q.order_by(AuditEvent.timestamp.desc()).offset(offset).limit(limit).all()
    return [_audit(a) for a in rows]


@router.get("/audit/{entity_type}/{entity_id}")
def audit_entity(entity_type: str, entity_id: str, db: DbDep, user: UserDep) -> list[dict]:
    rows = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
        .order_by(AuditEvent.timestamp.asc())
        .all()
    )
    return [_audit(a) for a in rows]


@router.get("/integrations")
def integrations(user: UserDep) -> list[dict]:
    return integration_status()


@router.post("/integrations/webhook/ticket")
def webhook_ticket(payload: WebhookTicket, db: DbDep) -> dict:
    ticket = create_ticket(db, payload.model_dump(), actor_id="webhook")
    return {"id": ticket.id, "ticket_number": ticket.ticket_number, "status": ticket.status}


@router.get("/test-runs")
def test_runs(db: DbDep, user: UserDep) -> list[dict]:
    rows = db.query(TestRun).order_by(TestRun.created_at.desc()).limit(50).all()
    return [
        {
            "id": r.id,
            "proposal_id": r.proposal_id,
            "status": r.status,
            "total_cases": r.total_cases,
            "unchanged_cases": r.unchanged_cases,
            "intentionally_changed_cases": r.intentionally_changed_cases,
            "unexpected_changed_cases": r.unexpected_changed_cases,
            "new_false_positives": r.new_false_positives,
            "new_false_negatives": r.new_false_negatives,
            "duration_ms": r.duration_ms,
            "regression_safety": r.regression_safety,
        }
        for r in rows
    ]


@router.get("/test-runs/{run_id}")
def test_run(run_id: str, db: DbDep, user: UserDep) -> dict:
    run = db.get(TestRun, run_id)
    results = db.query(TestResult).filter(TestResult.run_id == run_id).all()
    return {
        "id": run.id if run else run_id,
        "summary": json.loads(run.summary) if run and run.summary else {},
        "results": [
            {
                "review_id": r.review_id,
                "classification": r.classification,
                "baseline_flags": json.loads(r.baseline_flags or "[]"),
                "proposed_flags": json.loads(r.proposed_flags or "[]"),
                "notes": r.notes,
            }
            for r in results
        ],
    }


@router.get("/citations")
def citations(db: DbDep, user: UserDep) -> list[dict]:
    rows = db.query(ScientificCitation).order_by(ScientificCitation.year.desc()).all()
    return [
        {
            "citation_id": c.citation_id,
            "title": c.title,
            "authors": c.authors,
            "year": c.year,
            "journal": c.journal,
            "doi": c.doi,
            "status": c.status,
            "source": c.source,
            "is_synthetic": c.is_synthetic,
        }
        for c in rows
    ]


@router.get("/events/stream/{ticket_id}")
async def stream_events(ticket_id: str, request: Request):
    async def gen():
        import asyncio

        from app.db.session import SessionLocal

        last_seq = 0
        while True:
            if await request.is_disconnected():
                break
            db = SessionLocal()
            try:
                rows = (
                    db.query(WorkflowEvent)
                    .filter(WorkflowEvent.ticket_id == ticket_id, WorkflowEvent.sequence > last_seq)
                    .order_by(WorkflowEvent.sequence.asc())
                    .all()
                )
                for row in rows:
                    last_seq = row.sequence
                    yield {
                        "event": "workflow",
                        "data": json.dumps(
                            {
                                "sequence": row.sequence,
                                "event_type": row.event_type,
                                "message": row.message,
                                "timestamp": row.timestamp.isoformat(),
                            }
                        ),
                    }
            finally:
                db.close()
            await asyncio.sleep(0.7)

    return EventSourceResponse(gen())


def _audit(a: AuditEvent) -> dict:
    return {
        "id": a.id,
        "event_type": a.event_type,
        "entity_type": a.entity_type,
        "entity_id": a.entity_id,
        "actor_type": a.actor_type,
        "actor_id": a.actor_id,
        "timestamp": a.timestamp.isoformat(),
        "checksum": a.checksum,
        "correlation_id": a.correlation_id,
        "ticket_id": a.ticket_id,
        "metadata": json.loads(a.extra_metadata or "{}"),
    }
