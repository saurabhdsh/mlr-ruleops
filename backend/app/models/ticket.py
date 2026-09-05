from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class Ticket(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "tickets"
    __table_args__ = (
        UniqueConstraint("source_system", "external_id", name="uq_ticket_source_external"),
    )

    ticket_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_system: Mapped[str] = mapped_column(String(32), default="INTERNAL")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requester_name: Mapped[str] = mapped_column(String(255), default="")
    requester_email: Mapped[str] = mapped_column(String(255), default="")
    priority: Mapped[str] = mapped_column(String(16), default="MEDIUM")
    status: Mapped[str] = mapped_column(String(32), default="RECEIVED", index=True)
    market_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    brand_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    therapeutic_area_hint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)
    change_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(16), nullable=True)
    hitl_gate: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    autonomy_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    expected_target_rule: Mapped[str | None] = mapped_column(String(160), nullable=True)
    match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    owner_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_proposal_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    processing_lock: Mapped[int] = mapped_column(Integer, default=0)
    is_demo_seed: Mapped[bool] = mapped_column(default=False)

    attachments: Mapped[list["TicketAttachment"]] = relationship(back_populates="ticket")
    comments: Mapped[list["TicketComment"]] = relationship(back_populates="ticket")
    analyses: Mapped[list["TicketAnalysis"]] = relationship(back_populates="ticket")


class TicketAttachment(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "ticket_attachments"

    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(128), default="text/plain")
    content: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(64), default="upload")

    ticket: Mapped[Ticket] = relationship(back_populates="attachments")


class TicketComment(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "ticket_comments"

    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    author_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    author_type: Mapped[str] = mapped_column(String(16), default="USER")
    body: Mapped[str] = mapped_column(Text)

    ticket: Mapped[Ticket] = relationship(back_populates="comments")


class TicketAnalysis(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "ticket_analysis"

    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    provider_name: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(128))
    is_local_fallback: Mapped[bool] = mapped_column(default=False)
    prompt_template_version: Mapped[str] = mapped_column(String(64))
    output_schema_version: Mapped[str] = mapped_column(String(64))
    structured_output: Mapped[str] = mapped_column(Text)  # JSON
    decision_summary: Mapped[str] = mapped_column(Text, default="")
    overall_confidence: Mapped[float] = mapped_column(default=0.0)
    sources_used: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ticket: Mapped[Ticket] = relationship(back_populates="analyses")
    entities: Mapped[list["ExtractedEntity"]] = relationship(back_populates="analysis")


class ExtractedEntity(Base, UUIDPkMixin):
    __tablename__ = "extracted_entities"

    analysis_id: Mapped[str] = mapped_column(String(36), ForeignKey("ticket_analysis.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(default=0.0)
    source_span: Mapped[str | None] = mapped_column(String(500), nullable=True)

    analysis: Mapped[TicketAnalysis] = relationship(back_populates="entities")
