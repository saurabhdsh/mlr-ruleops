from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class ValidationRun(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "validation_runs"

    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("change_proposals.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    overall_status: Mapped[str] = mapped_column(String(16), default="PASS")
    blocking: Mapped[bool] = mapped_column(default=False)
    summary: Mapped[str] = mapped_column(Text, default="")

    results: Mapped[list["ValidationResult"]] = relationship(back_populates="run")


class ValidationResult(Base, UUIDPkMixin):
    __tablename__ = "validation_results"

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("validation_runs.id"), index=True)
    validator_name: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    severity: Mapped[str] = mapped_column(String(16), default="INFO")
    message: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str] = mapped_column(Text, default="{}")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    run: Mapped[ValidationRun] = relationship(back_populates="results")


class HistoricalReview(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "historical_reviews"

    review_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    market: Mapped[str] = mapped_column(String(64), index=True)
    brand: Mapped[str] = mapped_column(String(64), index=True)
    therapeutic_area: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(16), default="EN")
    material_type: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    expected_flags: Mapped[str] = mapped_column(Text, default="[]")
    expected_route: Mapped[str | None] = mapped_column(String(128), nullable=True)
    historical_decision: Mapped[str] = mapped_column(String(64), default="APPROVED")
    is_synthetic: Mapped[bool] = mapped_column(default=True)
    tags: Mapped[str] = mapped_column(Text, default="[]")


class TestCase(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "test_cases"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    market: Mapped[str | None] = mapped_column(String(64), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    therapeutic_area: Mapped[str | None] = mapped_column(String(64), nullable=True)
    material_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    expected_flags: Mapped[str] = mapped_column(Text, default="[]")
    expected_route: Mapped[str | None] = mapped_column(String(128), nullable=True)
    case_type: Mapped[str] = mapped_column(String(32), default="REGRESSION")


class TestRun(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "test_runs"

    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("change_proposals.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_cases: Mapped[int] = mapped_column(Integer, default=0)
    intentionally_changed_cases: Mapped[int] = mapped_column(Integer, default=0)
    unexpected_changed_cases: Mapped[int] = mapped_column(Integer, default=0)
    new_false_positives: Mapped[int] = mapped_column(Integer, default=0)
    new_false_negatives: Mapped[int] = mapped_column(Integer, default=0)
    baseline_flag_rate: Mapped[float] = mapped_column(Float, default=0.0)
    proposed_flag_rate: Mapped[float] = mapped_column(Float, default=0.0)
    flag_rate_delta: Mapped[float] = mapped_column(Float, default=0.0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    regression_safety: Mapped[str] = mapped_column(String(16), default="PASS")
    summary: Mapped[str] = mapped_column(Text, default="")

    results: Mapped[list["TestResult"]] = relationship(back_populates="run")


class TestResult(Base, UUIDPkMixin):
    __tablename__ = "test_results"

    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("test_runs.id"), index=True)
    review_id: Mapped[str] = mapped_column(String(64), index=True)
    classification: Mapped[str] = mapped_column(String(32))
    baseline_flags: Mapped[str] = mapped_column(Text, default="[]")
    proposed_flags: Mapped[str] = mapped_column(Text, default="[]")
    baseline_route: Mapped[str | None] = mapped_column(String(128), nullable=True)
    proposed_route: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    run: Mapped[TestRun] = relationship(back_populates="results")


class ImpactAnalysis(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "impact_analyses"

    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("change_proposals.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    modified_rules: Mapped[int] = mapped_column(Integer, default=0)
    markets_affected: Mapped[str] = mapped_column(Text, default="[]")
    brands_affected: Mapped[str] = mapped_column(Text, default="[]")
    material_types_affected: Mapped[str] = mapped_column(Text, default="[]")
    dependent_rules_inspected: Mapped[int] = mapped_column(Integer, default=0)
    historical_records_affected: Mapped[int] = mapped_column(Integer, default=0)
    unrelated_markets_impacted: Mapped[int] = mapped_column(Integer, default=0)
    unrelated_brands_impacted: Mapped[int] = mapped_column(Integer, default=0)
    summary_json: Mapped[str] = mapped_column(Text, default="{}")


class RiskAssessment(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "risk_assessments"

    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("change_proposals.id"), index=True)
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    overall_level: Mapped[str] = mapped_column(String(16))
    dimensions_json: Mapped[str] = mapped_column(Text)
    rationale: Mapped[str] = mapped_column(Text, default="")
    policy_gate: Mapped[str] = mapped_column(String(64), default="")
    ai_summary: Mapped[str] = mapped_column(Text, default="")
