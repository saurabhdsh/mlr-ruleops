from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.testing_engine.regression import CaseResult, TestClassification


@dataclass
class ImpactReport:
    modified_rules: int
    markets_affected: list[str]
    brands_affected: list[str]
    material_types_affected: list[str]
    dependent_rules_inspected: int
    historical_records_affected: int
    unrelated_markets_impacted: int
    unrelated_brands_impacted: int
    potential_content_reviews_affected: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "modified_rules": self.modified_rules,
            "markets_affected": self.markets_affected,
            "brands_affected": self.brands_affected,
            "material_types_affected": self.material_types_affected,
            "dependent_rules_inspected": self.dependent_rules_inspected,
            "historical_records_affected": self.historical_records_affected,
            "unrelated_markets_impacted": self.unrelated_markets_impacted,
            "unrelated_brands_impacted": self.unrelated_brands_impacted,
            "potential_content_reviews_affected": self.potential_content_reviews_affected,
        }


class ImpactAnalyzer:
    def analyze(
        self,
        target_scope: dict[str, Any],
        case_results: list[CaseResult],
        reviews: list[dict[str, Any]],
        dependent_count: int = 0,
        modified_rules: int = 1,
    ) -> ImpactReport:
        review_by_id = {r.get("review_id"): r for r in reviews}
        changed = [
            c
            for c in case_results
            if c.classification != TestClassification.UNCHANGED
        ]
        markets = set()
        brands = set()
        materials = set()
        intended_market = (target_scope.get("market") or "").lower()
        intended_brand = (target_scope.get("brand") or "").lower()
        unrelated_markets = set()
        unrelated_brands = set()

        for case in changed:
            review = review_by_id.get(case.review_id, {})
            m = review.get("market")
            b = review.get("brand")
            mt = review.get("material_type")
            if m:
                markets.add(m)
                if intended_market and m.lower() != intended_market:
                    unrelated_markets.add(m)
            if b:
                brands.add(b)
                if intended_brand and b.lower() != intended_brand:
                    unrelated_brands.add(b)
            if mt:
                materials.add(mt)

        if target_scope.get("market"):
            markets.add(target_scope["market"])
        if target_scope.get("brand"):
            brands.add(target_scope["brand"])

        return ImpactReport(
            modified_rules=modified_rules,
            markets_affected=sorted(markets),
            brands_affected=sorted(brands),
            material_types_affected=sorted(materials),
            dependent_rules_inspected=dependent_count,
            historical_records_affected=len(changed),
            unrelated_markets_impacted=len(unrelated_markets),
            unrelated_brands_impacted=len(unrelated_brands),
            potential_content_reviews_affected=len(changed),
        )
