from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import ActorType
from app.models.audit import AuditEvent, WorkflowEvent


class AuditLedger:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str,
        actor_type: str = ActorType.SYSTEM,
        actor_id: str = "system",
        previous_state: Any = None,
        new_state: Any = None,
        metadata: dict | None = None,
        correlation_id: str | None = None,
        ticket_id: str | None = None,
        checksum: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            timestamp=datetime.now(UTC),
            previous_state=json.dumps(previous_state) if previous_state is not None else None,
            new_state=json.dumps(new_state) if new_state is not None else None,
            extra_metadata=json.dumps(metadata or {}),
            correlation_id=correlation_id,
            ticket_id=ticket_id,
            checksum=checksum,
        )
        self.db.add(event)
        self.db.flush()
        return event

    def workflow(
        self,
        ticket_id: str,
        event_type: str,
        message: str,
        payload: dict | None = None,
        sequence: int = 0,
        actor_type: str = ActorType.WORKER,
    ) -> WorkflowEvent:
        ev = WorkflowEvent(
            ticket_id=ticket_id,
            sequence=sequence,
            event_type=event_type,
            message=message,
            payload=json.dumps(payload or {}),
            timestamp=datetime.now(UTC),
            actor_type=actor_type,
        )
        self.db.add(ev)
        self.db.flush()
        return ev
