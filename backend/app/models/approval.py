from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class ApprovalPolicy(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "approval_policies"

    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    condition_json: Mapped[str] = mapped_column(Text)
    required_roles: Mapped[str] = mapped_column(Text)  # JSON list
    governance_label: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(default=True)
    priority: Mapped[int] = mapped_column(default=100)


class ApprovalRequest(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "approval_requests"

    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("change_proposals.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    policy_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("approval_policies.id"), nullable=True)
    required_roles: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    risk_level_at_request: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    proposal_checksum: Mapped[str] = mapped_column(String(64), default="")

    decisions: Mapped[list["ApprovalDecision"]] = relationship(back_populates="request")


class ApprovalDecision(Base, UUIDPkMixin):
    __tablename__ = "approval_decisions"

    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("approval_requests.id"), index=True)
    approver_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    approver_role: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str] = mapped_column(Text, default="")
    proposal_id: Mapped[str] = mapped_column(String(36))
    rule_version_id: Mapped[str] = mapped_column(String(36))
    risk_score_at_approval: Mapped[str] = mapped_column(String(16))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    request: Mapped[ApprovalRequest] = relationship(back_populates="decisions")
