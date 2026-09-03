from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class RuleDefinition(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "rule_definitions"

    rule_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    rule_type: Mapped[str] = mapped_column(String(16))  # TEXT | LOGIC
    rule_category: Mapped[str] = mapped_column(String(64), default="DISCLAIMER")
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    description: Mapped[str] = mapped_column(Text, default="")
    production_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    lock_version: Mapped[int] = mapped_column(Integer, default=1)

    scopes: Mapped[list["RuleScope"]] = relationship(back_populates="rule")
    versions: Mapped[list["RuleVersion"]] = relationship(back_populates="rule")


class RuleScope(Base, UUIDPkMixin):
    __tablename__ = "rule_scopes"

    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_definitions.id"), index=True)
    scope_type: Mapped[str] = mapped_column(String(32))
    market: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    therapeutic_area: Mapped[str | None] = mapped_column(String(64), nullable=True)
    material_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rule: Mapped[RuleDefinition] = relationship(back_populates="scopes")


class RuleVersion(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "rule_versions"
    __table_args__ = (UniqueConstraint("rule_id", "version_number", name="uq_rule_version"),)

    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_definitions.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    version_label: Mapped[str] = mapped_column(String(32))
    body_json: Mapped[str] = mapped_column(Text)
    checksum_sha256: Mapped[str] = mapped_column(String(64), index=True)
    created_by: Mapped[str] = mapped_column(String(36), default="system")
    change_summary: Mapped[str] = mapped_column(Text, default="")
    is_production: Mapped[bool] = mapped_column(default=False)
    parent_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    rule: Mapped[RuleDefinition] = relationship(back_populates="versions")


class RuleDependency(Base, UUIDPkMixin):
    __tablename__ = "rule_dependencies"

    rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_definitions.id"), index=True)
    depends_on_rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_definitions.id"))
    dependency_type: Mapped[str] = mapped_column(String(64), default="REQUIRES")
    notes: Mapped[str] = mapped_column(Text, default="")


class RuleInheritance(Base, UUIDPkMixin):
    __tablename__ = "rule_inheritance"

    child_rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_definitions.id"), index=True)
    parent_rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_definitions.id"))
    inheritance_type: Mapped[str] = mapped_column(String(32), default="OVERRIDE")
    notes: Mapped[str] = mapped_column(Text, default="")


class ChangeRequest(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "change_requests"

    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    change_type: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="OPEN")


class ChangeProposal(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "change_proposals"

    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey("tickets.id"), index=True)
    change_request_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("change_requests.id"), nullable=True
    )
    target_rule_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_definitions.id"))
    base_rule_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("rule_versions.id"))
    proposed_body_json: Mapped[str] = mapped_column(Text)
    proposed_checksum: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="DRAFT")
    is_stale: Mapped[bool] = mapped_column(default=False)
    approval_invalidated: Mapped[bool] = mapped_column(default=False)
    provider_name: Mapped[str] = mapped_column(String(64), default="deterministic")
    model_name: Mapped[str] = mapped_column(String(128), default="local-fallback")
    prompt_template_version: Mapped[str] = mapped_column(String(64), default="")
    output_schema_version: Mapped[str] = mapped_column(String(64), default="")
    decision_record: Mapped[str] = mapped_column(Text, default="")
    sources_used: Mapped[str] = mapped_column(Text, default="[]")
    semantic_diff_json: Mapped[str] = mapped_column(Text, default="{}")

    operations: Mapped[list["ChangeOperation"]] = relationship(back_populates="proposal")


class ChangeOperation(Base, UUIDPkMixin):
    __tablename__ = "change_operations"

    proposal_id: Mapped[str] = mapped_column(String(36), ForeignKey("change_proposals.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    operation: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(String(255), default="")
    value: Mapped[str] = mapped_column(Text, default="")
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    proposal: Mapped[ChangeProposal] = relationship(back_populates="operations")
