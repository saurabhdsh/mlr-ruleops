from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.enums import LogicActionType, LogicOperator
from app.rules.dsl import ConditionClause, LogicAction, LogicGroup, LogicRule, TextRule, parse_rule_body


@dataclass
class ReviewContext:
    market: str = ""
    brand: str = ""
    therapeutic_area: str = ""
    language: str = "EN"
    material_type: str = ""
    content: str = ""
    country: str = ""
    extras: dict[str, Any] = field(default_factory=dict)

    def get(self, name: str) -> Any:
        if hasattr(self, name):
            return getattr(self, name)
        return self.extras.get(name)


@dataclass
class ExecutionResult:
    flags: list[str] = field(default_factory=list)
    route: str | None = None
    warnings: list[str] = field(default_factory=list)
    rejects: list[str] = field(default_factory=list)
    required_disclaimers: list[str] = field(default_factory=list)
    required_references: list[str] = field(default_factory=list)
    replacements: list[dict[str, str]] = field(default_factory=list)
    matched_rule_ids: list[str] = field(default_factory=list)
    require_review: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "flags": sorted(set(self.flags)),
            "route": self.route,
            "warnings": self.warnings,
            "rejects": self.rejects,
            "required_disclaimers": self.required_disclaimers,
            "required_references": self.required_references,
            "matched_rule_ids": self.matched_rule_ids,
            "require_review": self.require_review,
        }


def _compare(operator: LogicOperator, left: Any, right: Any) -> bool:
    if operator == LogicOperator.EXISTS:
        return left is not None and left != ""
    if operator == LogicOperator.NOT_EXISTS:
        return left is None or left == ""
    if left is None:
        return False
    if operator == LogicOperator.EQ:
        return str(left).lower() == str(right).lower() if isinstance(left, str) else left == right
    if operator == LogicOperator.NEQ:
        return str(left).lower() != str(right).lower() if isinstance(left, str) else left != right
    if operator == LogicOperator.CONTAINS:
        return str(right).lower() in str(left).lower()
    if operator == LogicOperator.NOT_CONTAINS:
        return str(right).lower() not in str(left).lower()
    if operator == LogicOperator.STARTS_WITH:
        return str(left).lower().startswith(str(right).lower())
    if operator == LogicOperator.ENDS_WITH:
        return str(left).lower().endswith(str(right).lower())
    if operator == LogicOperator.IN:
        values = [str(v).lower() for v in (right or [])]
        return str(left).lower() in values
    if operator == LogicOperator.NOT_IN:
        values = [str(v).lower() for v in (right or [])]
        return str(left).lower() not in values
    try:
        lf, rf = float(left), float(right)
    except (TypeError, ValueError):
        return False
    if operator == LogicOperator.GT:
        return lf > rf
    if operator == LogicOperator.GTE:
        return lf >= rf
    if operator == LogicOperator.LT:
        return lf < rf
    if operator == LogicOperator.LTE:
        return lf <= rf
    return False


def evaluate_group(group: LogicGroup, ctx: ReviewContext) -> bool:
    if group.all is not None:
        return all(_eval_node(n, ctx) for n in group.all)
    if group.any is not None:
        return any(_eval_node(n, ctx) for n in group.any)
    if group.not_ is not None:
        return not _eval_node(group.not_, ctx)
    return False


def _eval_node(node: ConditionClause | LogicGroup, ctx: ReviewContext) -> bool:
    if isinstance(node, LogicGroup):
        return evaluate_group(node, ctx)
    return _compare(node.operator, ctx.get(node.field), node.value)


def apply_action(action: LogicAction, result: ExecutionResult) -> None:
    if action.type == LogicActionType.FLAG and action.value:
        result.flags.append(action.value)
    elif action.type == LogicActionType.ROUTE and action.target:
        result.route = action.target
    elif action.type == LogicActionType.WARN and action.value:
        result.warnings.append(action.value)
    elif action.type == LogicActionType.REJECT and action.value:
        result.rejects.append(action.value)
    elif action.type == LogicActionType.REQUIRE_DISCLAIMER and action.value:
        result.required_disclaimers.append(action.value)
    elif action.type == LogicActionType.REQUIRE_REFERENCE and action.value:
        result.required_references.append(action.value)
    elif action.type == LogicActionType.REPLACE_TEXT and action.value:
        result.replacements.append({"value": action.value, "field": action.field or ""})
    elif action.type == LogicActionType.REQUIRE_REVIEW:
        result.require_review = True


class RuleExecutionEngine:
    """Deterministic evaluator for TEXT and LOGIC rules."""

    def execute_rule(self, body: dict | str | TextRule | LogicRule, ctx: ReviewContext) -> ExecutionResult:
        result = ExecutionResult()
        rule = body if isinstance(body, (TextRule, LogicRule)) else parse_rule_body(body)
        if isinstance(rule, TextRule):
            self._execute_text(rule, ctx, result)
        else:
            self._execute_logic(rule, ctx, result)
        return result

    def execute_many(self, bodies: list[dict | str | TextRule | LogicRule], ctx: ReviewContext) -> ExecutionResult:
        merged = ExecutionResult()
        for body in bodies:
            part = self.execute_rule(body, ctx)
            merged.flags.extend(part.flags)
            if part.route:
                merged.route = part.route
            merged.warnings.extend(part.warnings)
            merged.rejects.extend(part.rejects)
            merged.required_disclaimers.extend(part.required_disclaimers)
            merged.required_references.extend(part.required_references)
            merged.replacements.extend(part.replacements)
            merged.matched_rule_ids.extend(part.matched_rule_ids)
            merged.require_review = merged.require_review or part.require_review
        merged.flags = sorted(set(merged.flags))
        return merged

    def _execute_text(self, rule: TextRule, ctx: ReviewContext, result: ExecutionResult) -> None:
        if not self._scope_match(rule, ctx):
            return
        content_l = (ctx.content or "").lower()
        matched = False
        for phrase in rule.required_phrases:
            if phrase.lower() not in content_l:
                result.flags.append(f"MISSING_REQUIRED_PHRASE:{phrase}")
                matched = True
        for term in rule.flagged_terms:
            if term.lower() in content_l:
                result.flags.append(f"RESTRICTED_TERM:{term}")
                matched = True
        for ref in rule.references:
            years = [p for p in ref.id.replace("-", " ").split() if p.isdigit()]
            present = ref.id.lower() in content_l or any(y in content_l for y in years)
            if present:
                result.flags.append(f"CITATION_PRESENT:{ref.id}")
                matched = True
            else:
                result.flags.append(f"MISSING_REQUIRED_CITATION:{ref.id}")
                matched = True
            result.required_references.append(ref.id)
        if matched or result.required_references or rule.content:
            result.matched_rule_ids.append(rule.rule_id)

    def _scope_match(self, rule: TextRule, ctx: ReviewContext) -> bool:
        scope = rule.scope
        pairs = [
            (scope.market, ctx.market),
            (scope.brand, ctx.brand),
            (scope.therapeutic_area, ctx.therapeutic_area),
            (scope.material_type, ctx.material_type),
            (scope.language, ctx.language),
        ]
        for needed, actual in pairs:
            if needed and actual and needed.lower() != actual.lower():
                return False
        return True

    def _execute_logic(self, rule: LogicRule, ctx: ReviewContext, result: ExecutionResult) -> None:
        if evaluate_group(rule.when, ctx):
            result.matched_rule_ids.append(rule.rule_id)
            for action in rule.actions:
                apply_action(action, result)
