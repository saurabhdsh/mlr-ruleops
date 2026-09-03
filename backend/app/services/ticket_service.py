from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit.ledger import AuditLedger
from app.core.enums import ActorType, SourceSystem, WorkflowState
from app.core.errors import RuleOpsError
from app.models.ticket import Ticket, TicketAttachment, TicketComment
from app.security.sanitize import sanitize_text


def next_ticket_number(db: Session) -> str:
    count = db.query(func.count(Ticket.id)).scalar() or 0
    return f"TKT-{1000 + count + 1}"


def create_ticket(db: Session, payload: dict, actor_id: str = "system") -> Ticket:
    external_id = payload.get("external_id")
    source = payload.get("source_system") or SourceSystem.INTERNAL
    if external_id:
        existing = (
            db.query(Ticket)
            .filter(Ticket.source_system == source, Ticket.external_id == external_id)
            .one_or_none()
        )
        if existing:
            return existing
    ticket = Ticket(
        ticket_number=payload.get("ticket_number") or next_ticket_number(db),
        external_id=external_id,
        source_system=source,
        title=sanitize_text(payload["title"], 500),
        description=sanitize_text(payload["description"]),
        requester_name=sanitize_text(payload.get("requester_name") or payload.get("requester") or "", 255),
        requester_email=sanitize_text(payload.get("requester_email") or "", 255),
        priority=payload.get("priority") or "MEDIUM",
        status=WorkflowState.RECEIVED,
        market_hint=payload.get("market_hint"),
        brand_hint=payload.get("brand_hint"),
        therapeutic_area_hint=payload.get("therapeutic_area_hint"),
        language_hint=payload.get("language_hint"),
        due_date=payload.get("due_date"),
        owner_id=payload.get("owner_id"),
    )
    db.add(ticket)
    db.flush()
    for att in payload.get("attachments") or []:
        db.add(
            TicketAttachment(
                ticket_id=ticket.id,
                filename=att.get("filename", "attachment.txt"),
                content_type=att.get("content_type", "text/plain"),
                content=att.get("content", ""),
                source_type=att.get("source_type", "upload"),
            )
        )
    AuditLedger(db).record(
        event_type="TICKET_RECEIVED",
        entity_type="ticket",
        entity_id=ticket.id,
        actor_type=ActorType.USER if actor_id != "system" else ActorType.INTEGRATION,
        actor_id=actor_id,
        ticket_id=ticket.id,
        new_state={"ticket_number": ticket.ticket_number, "source": ticket.source_system},
    )
    return ticket


def add_comment(db: Session, ticket_id: str, body: str, author_id: str | None, author_type: str = "USER") -> TicketComment:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise RuleOpsError("TICKET_NOT_FOUND", "Ticket not found", {"id": ticket_id}, False, 404)
    comment = TicketComment(
        ticket_id=ticket_id,
        author_id=author_id,
        author_type=author_type,
        body=sanitize_text(body),
    )
    db.add(comment)
    db.flush()
    return comment


def clarify_ticket(db: Session, ticket_id: str, note: str, actor_id: str) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise RuleOpsError("TICKET_NOT_FOUND", "Ticket not found", status_code=404)
    add_comment(db, ticket_id, note, actor_id)
    ticket.market_hint = ticket.market_hint
    ticket.updated_at = datetime.now(UTC)
    return ticket
