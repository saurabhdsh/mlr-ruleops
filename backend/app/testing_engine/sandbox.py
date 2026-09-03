from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.rules.engine import ExecutionResult, ReviewContext, RuleExecutionEngine


@dataclass
class CaseOutcome:
    review_id: str
    baseline: ExecutionResult
    proposed: ExecutionResult
    context: ReviewContext


@dataclass
class SandboxSession:
    production_rules: list[dict[str, Any]]
    proposed_override: dict[str, Any]
    target_rule_id: str
    engine: RuleExecutionEngine = field(default_factory=RuleExecutionEngine)

    def _active_bodies(self, override: bool) -> list[dict[str, Any]]:
        bodies = []
        for rule in self.production_rules:
            body = rule.get("body") if "body" in rule else rule
            rid = body.get("rule_id") or rule.get("rule_id")
            if override and rid == self.target_rule_id:
                bodies.append(self.proposed_override)
            else:
                bodies.append(body)
        if override and not any(
            (b.get("rule_id") == self.target_rule_id) for b in bodies
        ):
            bodies.append(self.proposed_override)
        return bodies

    def execute_pair(self, ctx: ReviewContext) -> tuple[ExecutionResult, ExecutionResult]:
        baseline = self.engine.execute_many(self._active_bodies(False), ctx)
        proposed = self.engine.execute_many(self._active_bodies(True), ctx)
        return baseline, proposed

    def replay(self, reviews: list[dict[str, Any]]) -> list[CaseOutcome]:
        outcomes = []
        for review in reviews:
            ctx = ReviewContext(
                market=review.get("market", ""),
                brand=review.get("brand", ""),
                therapeutic_area=review.get("therapeutic_area", ""),
                language=review.get("language", "EN"),
                material_type=review.get("material_type", ""),
                content=review.get("content", ""),
            )
            baseline, proposed = self.execute_pair(ctx)
            outcomes.append(
                CaseOutcome(
                    review_id=review.get("review_id", ""),
                    baseline=baseline,
                    proposed=proposed,
                    context=ctx,
                )
            )
        return outcomes
