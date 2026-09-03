from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class Deployment(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "deployments"

    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("change_proposals.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_definitions.id"))
    from_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_versions.id"))
    to_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_versions.id"))
    deployed_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(32), default="SUCCESS")
    smoke_test_status: Mapped[str] = mapped_column(String(16), default="PASS")
    smoke_test_notes: Mapped[str] = mapped_column(Text, default="")
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RollbackEvent(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "rollback_events"

    deployment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("deployments.id"), nullable=True
    )
    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_definitions.id"))
    from_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_versions.id"))
    to_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_versions.id"))
    reason: Mapped[str] = mapped_column(Text)
    rolled_back_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    smoke_test_status: Mapped[str] = mapped_column(String(16), default="PASS")
    ticket_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
