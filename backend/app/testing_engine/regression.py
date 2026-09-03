from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.enums import TestClassification
from app.testing_engine.sandbox import CaseOutcome, SandboxSession


@dataclass
class CaseResult:
    review_id: str
    classification: str
    baseline_flags: list[str]
    proposed_flags: list[str]
    baseline_route: str | None
    proposed_route: str | None
    notes: str = ""


@dataclass
class RegressionReport:
    total_cases: int
    unchanged_cases: int
    intentionally_changed_cases: int
    unexpected_changed_cases: int
    new_false_positives: int
    new_false_negatives: int
    baseline_flag_rate: float
    proposed_flag_rate: float
    flag_rate_delta: float
    regression_safety: str
    results: list[CaseResult] = field(default_factory=list)
    syntax_errors: int = 0
    conflicts: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "unchanged_cases": self.unchanged_cases,
            "intentionally_changed_cases": self.intentionally_changed_cases,
            "unexpected_changed_cases": self.unexpected_changed_cases,
            "new_false_positives": self.new_false_positives,
            "new_false_negatives": self.new_false_negatives,
            "baseline_flag_rate": self.baseline_flag_rate,
            "proposed_flag_rate": self.proposed_flag_rate,
            "flag_rate_delta": self.flag_rate_delta,
            "regression_safety": self.regression_safety,
            "syntax_errors": self.syntax_errors,
            "conflicts": self.conflicts,
        }


def _flagged(flags: list[str]) -> bool:
    return len(flags) > 0


class RegressionEngine:
    """Compare production vs proposed execution on historical reviews."""

    def run(
        self,
        session: SandboxSession,
        reviews: list[dict[str, Any]],
        intended_scope: dict[str, Any] | None = None,
    ) -> RegressionReport:
        intended_scope = intended_scope or {}
        outcomes = session.replay(reviews)
        results: list[CaseResult] = []
        unchanged = intentional = unexpected = fp = fn = 0
        baseline_flagged = 0
        proposed_flagged = 0

        for outcome in outcomes:
            classification, notes = self._classify(outcome, intended_scope)
            if classification == TestClassification.UNCHANGED:
                unchanged += 1
            elif classification == TestClassification.EXPECTED_CHANGE:
                intentional += 1
            elif classification == TestClassification.UNEXPECTED_CHANGE:
                unexpected += 1
            elif classification == TestClassification.FALSE_POSITIVE:
                fp += 1
                unexpected += 1
            elif classification == TestClassification.FALSE_NEGATIVE:
                fn += 1
                unexpected += 1

            if _flagged(outcome.baseline.flags):
                baseline_flagged += 1
            if _flagged(outcome.proposed.flags):
                proposed_flagged += 1

            results.append(
                CaseResult(
                    review_id=outcome.review_id,
                    classification=classification,
                    baseline_flags=outcome.baseline.flags,
                    proposed_flags=outcome.proposed.flags,
                    baseline_route=outcome.baseline.route,
                    proposed_route=outcome.proposed.route,
                    notes=notes,
                )
            )

        total = len(outcomes) or 1
        b_rate = baseline_flagged / total
        p_rate = proposed_flagged / total
        safety = "PASS" if unexpected == 0 and fp == 0 and fn == 0 else "FAIL"
        return RegressionReport(
            total_cases=len(outcomes),
            unchanged_cases=unchanged,
            intentionally_changed_cases=intentional,
            unexpected_changed_cases=unexpected,
            new_false_positives=fp,
            new_false_negatives=fn,
            baseline_flag_rate=round(b_rate, 4),
            proposed_flag_rate=round(p_rate, 4),
            flag_rate_delta=round(p_rate - b_rate, 4),
            regression_safety=safety,
            results=results,
        )

    def _classify(self, outcome: CaseOutcome, intended_scope: dict[str, Any]) -> tuple[str, str]:
        b_flags = set(outcome.baseline.flags)
        p_flags = set(outcome.proposed.flags)
        same = b_flags == p_flags and outcome.baseline.route == outcome.proposed.route
        if same:
            return TestClassification.UNCHANGED, "No behavioral difference"

        in_scope = self._in_intended_scope(outcome, intended_scope)
        expected_flags = set(intended_scope.get("expected_flag_tokens") or [])
        # Citation swap: MISSING_REQUIRED_CITATION:* change is intended when in market/brand/area
        citation_swap = any("MISSING_REQUIRED_CITATION" in f or "CITATION_PRESENT" in f for f in b_flags | p_flags)
        if in_scope and (citation_swap or (expected_flags & (b_flags.symmetric_difference(p_flags)))):
            return TestClassification.EXPECTED_CHANGE, "Change confined to intended scope"

        # Scope leakage: change outside intended market/brand
        if not in_scope:
            added = p_flags - b_flags
            removed = b_flags - p_flags
            if added:
                return TestClassification.FALSE_POSITIVE, "Unexpected additional flags outside intended scope"
            if removed:
                return TestClassification.FALSE_NEGATIVE, "Required flags dropped outside intended scope"
            return TestClassification.UNEXPECTED_CHANGE, "Behavior changed outside intended scope"

        added = p_flags - b_flags
        removed = b_flags - p_flags
        if added and not removed:
            return TestClassification.EXPECTED_CHANGE, "Additional in-scope flags from proposed rule"
        if removed and not added:
            return TestClassification.EXPECTED_CHANGE, "In-scope flags removed by proposed rule"
        return TestClassification.EXPECTED_CHANGE, "In-scope behavioral change"

    def _in_intended_scope(self, outcome: CaseOutcome, intended_scope: dict[str, Any]) -> bool:
        market = (intended_scope.get("market") or "").lower()
        brand = (intended_scope.get("brand") or "").lower()
        area = (intended_scope.get("therapeutic_area") or "").lower()
        if market and outcome.context.market.lower() != market:
            return False
        if brand and outcome.context.brand.lower() != brand:
            return False
        if area and outcome.context.therapeutic_area.lower() != area:
            return False
        return True
