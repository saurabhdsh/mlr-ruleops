from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.enums import LogicActionType, LogicOperator


class ConditionClause(BaseModel):
    field: str
    operator: LogicOperator
    value: Any = None


class LogicGroup(BaseModel):
    all: list[ConditionClause | LogicGroup] | None = None
    any: list[ConditionClause | LogicGroup] | None = None
    not_: ConditionClause | LogicGroup | None = Field(default=None, alias="not")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def one_combinator(self) -> LogicGroup:
        present = sum(1 for x in (self.all, self.any, self.not_) if x is not None)
        if present != 1:
            raise ValueError("Logic group must have exactly one of: all, any, not")
        return self


class LogicAction(BaseModel):
    type: LogicActionType
    target: str | None = None
    value: str | None = None
    field: str | None = None


class RuleScopePayload(BaseModel):
    market: str | None = None
    brand: str | None = None
    therapeutic_area: str | None = None
    country: str | None = None
    language: str | None = None
    material_type: str | None = None


class CitationRef(BaseModel):
    type: Literal["scientific_citation"] = "scientific_citation"
    id: str


class TextRule(BaseModel):
    rule_type: Literal["TEXT"] = "TEXT"
    rule_id: str
    field: str
    scope: RuleScopePayload = Field(default_factory=RuleScopePayload)
    content: str
    references: list[CitationRef] = Field(default_factory=list)
    flagged_terms: list[str] = Field(default_factory=list)
    required_phrases: list[str] = Field(default_factory=list)


class LogicRule(BaseModel):
    rule_type: Literal["LOGIC"] = "LOGIC"
    rule_id: str
    when: LogicGroup
    actions: list[LogicAction]
    scope: RuleScopePayload = Field(default_factory=RuleScopePayload)

    @field_validator("actions")
    @classmethod
    def actions_not_empty(cls, v: list[LogicAction]) -> list[LogicAction]:
        if not v:
            raise ValueError("LOGIC rule must have at least one action")
        return v


class ChangeIntentField(BaseModel):
    value: str | None = None
    confidence: float = 0.0


class ChangeIntent(BaseModel):
    change_type: str
    intent: str
    market: ChangeIntentField = Field(default_factory=ChangeIntentField)
    brand: ChangeIntentField = Field(default_factory=ChangeIntentField)
    therapeutic_area: ChangeIntentField = Field(default_factory=ChangeIntentField)
    language: ChangeIntentField = Field(default_factory=ChangeIntentField)
    material_type: ChangeIntentField = Field(default_factory=ChangeIntentField)
    rule_category: ChangeIntentField = Field(default_factory=ChangeIntentField)
    string_type: ChangeIntentField = Field(default_factory=ChangeIntentField)
    operation: str = ""
    old_value: str | None = None
    new_value: str | None = None
    citation_to_remove: str | None = None
    citation_to_add: str | None = None
    remove_reference: str | None = None
    add_reference: str | None = None
    routing_target: str | None = None
    constraint: str | None = None
    effective_date: str | None = None
    business_reason: str = ""
    risk_indicators: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    requires_scientific_verification: bool = False
    overall_confidence: float = 0.0
    decision_summary: str = ""


class MutationOperation(BaseModel):
    operation: str
    value: Any = None
    path: str | None = None
    old_value: Any = None


class ChangeProposalPayload(BaseModel):
    change_type: str
    target_rule_id: str
    operations: list[MutationOperation]
    reason: str = ""


def parse_rule_body(body: dict[str, Any] | str) -> TextRule | LogicRule:
    if isinstance(body, str):
        import json

        body = json.loads(body)
    rule_type = body.get("rule_type")
    if rule_type == "TEXT":
        return TextRule.model_validate(body)
    if rule_type == "LOGIC":
        return LogicRule.model_validate(body)
    raise ValueError(f"Unsupported rule_type: {rule_type}")


# Back-compat aliases used in imports
LogicCondition = ConditionClause
