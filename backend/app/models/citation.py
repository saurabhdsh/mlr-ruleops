from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class ScientificCitation(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "scientific_citations"

    citation_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    authors: Mapped[str] = mapped_column(Text)
    year: Mapped[int] = mapped_column(Integer)
    journal: Mapped[str] = mapped_column(String(255))
    doi: Mapped[str] = mapped_column(String(255), default="")
    study_type: Mapped[str] = mapped_column(String(64), default="RCT")
    status: Mapped[str] = mapped_column(String(64), default="SYNTHETIC_DEMO")
    source: Mapped[str] = mapped_column(String(128), default="Synthetic Demo Dataset")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(default=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class ReferenceSource(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "reference_sources"

    source_id: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(64))
    uri: Mapped[str] = mapped_column(String(500), default="")
    snippet: Mapped[str] = mapped_column(Text, default="")
    relevance_note: Mapped[str] = mapped_column(Text, default="")
    is_synthetic: Mapped[bool] = mapped_column(default=True)
