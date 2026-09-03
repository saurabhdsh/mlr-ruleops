from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.enums import RuleScopeType
from app.rules.dsl import ChangeIntent

SCOPE_RANK = {
    RuleScopeType.MARKET_BRAND: 400,
    RuleScopeType.BRAND: 300,
    RuleScopeType.MARKET: 200,
    RuleScopeType.UNIVERSAL: 100,
    RuleScopeType.SCIENTIFIC_ACCURACY: 150,
}


@dataclass
class RuleCandidate:
    rule_pk: str
    rule_id: str
    name: str
    scope_type: str
    market: str | None
    brand: str | None
    therapeutic_area: str | None
    material_type: str | None
    category: str
    priority: int
    match_score: float
    reasons: list[str] = field(default_factory=list)
    rejected_reason: str | None = None


@dataclass
class ResolutionResult:
    selected: RuleCandidate | None
    candidates: list[RuleCandidate]
    hierarchy_path: list[str]
    inherited_rule_ids: list[str]
    overridden_rule_ids: list[str]
    explanation: str
    confidence: float
    dependencies: list[str] = field(default_factory=list)


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _eq(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return _norm(a) == _norm(b)


class RuleResolver:
    """Deterministic hierarchy resolver.

    Priority: MARKET_BRAND > BRAND > MARKET > UNIVERSAL
    Scientific Accuracy overlays when category/policy matches.
    """

    def resolve(
        self,
        intent: ChangeIntent,
        rules: list[dict[str, Any]],
        inheritances: list[dict[str, Any]] | None = None,
        dependencies: list[dict[str, Any]] | None = None,
    ) -> ResolutionResult:
        inheritances = inheritances or []
        dependencies = dependencies or []
        market = intent.market.value
        brand = intent.brand.value
        area = intent.therapeutic_area.value
        material = intent.material_type.value
        category = intent.rule_category.value

        scored: list[RuleCandidate] = []
        for rule in rules:
            if rule.get("status") not in (None, "ACTIVE", "DRAFT"):
                continue
            if rule.get("market") and market and not _eq(rule.get("market"), market):
                continue
            if rule.get("brand") and brand and not _eq(rule.get("brand"), brand):
                continue
            candidate = self._score(rule, market, brand, area, material, category)
            if candidate.match_score > 0:
                scored.append(candidate)

        scored.sort(key=lambda c: (c.match_score, -c.priority, SCOPE_RANK.get(RuleScopeType(c.scope_type), 0)), reverse=True)

        selected = scored[0] if scored else None
        overridden: list[str] = []
        inherited: list[str] = []
        if selected:
            for other in scored[1:]:
                if self._is_overridden_by(other, selected):
                    other.rejected_reason = (
                        f"{other.scope_type.lower()}-level rule is overridden by the more specific "
                        f"{selected.scope_type} rule {selected.rule_id}."
                    )
                    overridden.append(other.rule_id)
            for inh in inheritances:
                if inh.get("child_rule_id") == selected.rule_pk:
                    inherited.append(inh.get("parent_rule_id", ""))

        path = self._hierarchy_path(selected, market, brand, area, material)
        explanation = self._explain(selected, scored, market, brand, area, category)
        confidence = min(0.99, (selected.match_score / 100.0) if selected else 0.0)
        if selected and len(scored) > 1:
            gap = selected.match_score - scored[1].match_score
            if gap < 8:
                confidence = min(confidence, 0.74)

        dep_ids = []
        if selected:
            dep_ids = [
                d.get("depends_on_rule_id", "")
                for d in dependencies
                if d.get("rule_id") == selected.rule_pk
            ]

        return ResolutionResult(
            selected=selected,
            candidates=scored,
            hierarchy_path=path,
            inherited_rule_ids=[x for x in inherited if x],
            overridden_rule_ids=overridden,
            explanation=explanation,
            confidence=round(confidence, 4),
            dependencies=dep_ids,
        )

    def _score(
        self,
        rule: dict[str, Any],
        market: str | None,
        brand: str | None,
        area: str | None,
        material: str | None,
        category: str | None,
    ) -> RuleCandidate:
        scope_type = rule.get("scope_type") or RuleScopeType.UNIVERSAL
        score = 0.0
        reasons: list[str] = []

        score += SCOPE_RANK.get(RuleScopeType(scope_type), 50) / 10

        if _eq(rule.get("market"), market):
            score += 25
            reasons.append(f"exact {rule.get('market')} market match")
        elif rule.get("market") and market:
            score -= 15

        if _eq(rule.get("brand"), brand):
            score += 25
            reasons.append(f"exact {rule.get('brand')} brand match")
        elif rule.get("brand") and brand:
            score -= 15

        if _eq(rule.get("therapeutic_area"), area):
            score += 18
            reasons.append(f"exact {rule.get('therapeutic_area')} match")
        elif rule.get("therapeutic_area") and area:
            score -= 8

        if _eq(rule.get("material_type"), material):
            score += 8
            reasons.append(f"exact {rule.get('material_type')} material match")

        if category and _eq(rule.get("rule_category"), category):
            score += 16
            reasons.append(f"exact {rule.get('rule_category')} category")
        elif category and "disclaimer" in (category or "").lower() and "disclaimer" in (rule.get("rule_category") or "").lower():
            score += 16
            reasons.append("disclaimer category match")

        return RuleCandidate(
            rule_pk=rule.get("id", ""),
            rule_id=rule.get("rule_id", ""),
            name=rule.get("name", ""),
            scope_type=str(scope_type),
            market=rule.get("market"),
            brand=rule.get("brand"),
            therapeutic_area=rule.get("therapeutic_area"),
            material_type=rule.get("material_type"),
            category=rule.get("rule_category", ""),
            priority=int(rule.get("priority", 100)),
            match_score=round(score, 2),
            reasons=reasons,
        )

    def _is_overridden_by(self, lesser: RuleCandidate, selected: RuleCandidate) -> bool:
        return SCOPE_RANK.get(RuleScopeType(selected.scope_type), 0) > SCOPE_RANK.get(
            RuleScopeType(lesser.scope_type), 0
        )

    def _hierarchy_path(
        self,
        selected: RuleCandidate | None,
        market: str | None,
        brand: str | None,
        area: str | None,
        material: str | None,
    ) -> list[str]:
        path = ["Universal"]
        if market:
            path.append(market)
        if brand:
            path.append(brand)
        if area:
            path.append(area)
        if material:
            path.append(material)
        if selected:
            path.append(selected.category or selected.name)
        return path

    def _explain(
        self,
        selected: RuleCandidate | None,
        scored: list[RuleCandidate],
        market: str | None,
        brand: str | None,
        area: str | None,
        category: str | None,
    ) -> str:
        if not selected:
            return (
                "No matching active rule was found for the extracted market, brand, "
                "therapeutic area, and category. Clarification is required."
            )
        parts = [
            f"Market identified as {market or 'unspecified'}.",
            f"Brand identified as {brand or 'unspecified'}.",
        ]
        if area:
            parts.append(f"Request concerns {area.lower()} {category or 'rule'}.")
        parts.append(f"{len(scored)} matching rule{'s' if len(scored) != 1 else ''} found.")
        why = "; ".join(selected.reasons) if selected.reasons else "highest specificity"
        parts.append(
            f"{selected.rule_id} selected because it provides the highest-specificity exact match ({why})."
        )
        for other in scored[1:3]:
            if other.rejected_reason:
                parts.append(f"{other.rule_id} not selected because {other.rejected_reason}")
        parts.append(f"Confidence {int(min(99, selected.match_score))}%.")
        return " ".join(parts)
