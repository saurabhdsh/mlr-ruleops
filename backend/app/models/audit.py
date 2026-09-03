from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import UUIDPkMixin


class AuditEvent(Base, UUIDPkMixin):
    __tablename__ = "audit_events"

    event_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    actor_type: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(String(64), default="system")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    previous_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_state: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[str] = mapped_column("metadata", Text, default="{}")
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ticket_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)


class WorkflowEvent(Base, UUIDPkMixin):
    __tablename__ = "workflow_events"

    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    sequence: Mapped[int] = mapped_column(default=0)
    event_type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[str] = mapped_column(Text, default="{}")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    actor_type: Mapped[str] = mapped_column(String(16), default="WORKER")
