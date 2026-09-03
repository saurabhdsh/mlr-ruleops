from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.enums import RiskLevel


LEVEL_ORDER = {RiskLevel.LOW: 1, RiskLevel.MEDIUM: 2, RiskLevel.HIGH: 3, RiskLevel.CRITICAL: 4}


@dataclass
class RiskReport:
    overall: str
    dimensions: dict[str, str]
    rationale: str
    policy_gate: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall,
            "dimensions": self.dimensions,
            "rationale": self.rationale,
            "policy_gate": self.policy_gate,
        }


def _max_level(*levels: str) -> str:
    return max(levels, key=lambda l: LEVEL_ORDER.get(RiskLevel(l), 0))


class RiskEngine:
    """Configurable, deterministic risk scoring. AI may summarize; this decides the gate."""

    def assess(
        self,
        *,
        category: str | None,
        scope_type: str | None,
        markets: list[str],
        brands: list[str],
        regression_safety: str,
        unexpected_changes: int,
        false_positives: int,
        false_negatives: int,
        citation_unverified: bool,
        logic_complexity: int = 0,
        flag_rate_delta: float = 0.0,
        scientific: bool = False,
    ) -> RiskReport:
        dims: dict[str, str] = {}

        sci = scientific or (category or "").upper() in {"DISCLAIMER", "SCIENTIFIC_ACCURACY", "CITATION"}
        dims["scientific_accuracy"] = RiskLevel.HIGH if sci else RiskLevel.LOW
        dims["regulatory_scope"] = (
            RiskLevel.HIGH if (scope_type or "") == "UNIVERSAL" else RiskLevel.MEDIUM if (scope_type or "") in {"MARKET", "MARKET_BRAND"} else RiskLevel.LOW
        )
        dims["market_scope"] = RiskLevel.MEDIUM if len(markets) == 1 else RiskLevel.HIGH if len(markets) > 1 else RiskLevel.LOW
        dims["brand_scope"] = RiskLevel.MEDIUM if len(brands) == 1 else RiskLevel.HIGH if len(brands) > 1 else RiskLevel.LOW
        dims["cross_brand_impact"] = RiskLevel.HIGH if len(brands) > 1 else RiskLevel.LOW
        dims["cross_market_impact"] = RiskLevel.HIGH if len(markets) > 1 else RiskLevel.LOW
        dims["logic_complexity"] = RiskLevel.HIGH if logic_complexity >= 5 else RiskLevel.MEDIUM if logic_complexity >= 3 else RiskLevel.LOW
        dims["regression_delta"] = (
            RiskLevel.HIGH
            if unexpected_changes > 0
            else RiskLevel.LOW
            if abs(flag_rate_delta) < 0.05
            else RiskLevel.MEDIUM
        )
        dims["false_positive_risk"] = RiskLevel.HIGH if false_positives > 0 else RiskLevel.LOW
        dims["false_negative_risk"] = RiskLevel.HIGH if false_negatives > 0 else RiskLevel.LOW
        dims["citation_verification"] = (
            RiskLevel.CRITICAL if citation_unverified else RiskLevel.MEDIUM if sci else RiskLevel.LOW
        )
        dims["deployment_scope"] = RiskLevel.MEDIUM if (scope_type or "") == "MARKET_BRAND" else RiskLevel.HIGH if (scope_type or "") == "UNIVERSAL" else RiskLevel.LOW

        overall = _max_level(*dims.values())
        if regression_safety == "FAIL":
            overall = _max_level(overall, RiskLevel.HIGH)

        rationale = (
            f"Scientific accuracy = {dims['scientific_accuracy']}. "
            f"Market scope = {dims['market_scope']}. "
            f"Cross-brand impact = {dims['cross_brand_impact']}. "
            f"Regression impact = {dims['regression_delta']}. "
            f"Overall = {overall}."
        )
        if citation_unverified:
            policy_gate = "BLOCK_CITATION_VERIFICATION"
        elif overall == RiskLevel.CRITICAL:
            policy_gate = "MEDICAL_REGULATORY_MLR"
        elif overall == RiskLevel.HIGH:
            policy_gate = "MLR_ADMIN"
        elif (scope_type or "") == "UNIVERSAL":
            policy_gate = "GOVERNANCE_BOARD"
        else:
            policy_gate = "STANDARD"

        return RiskReport(overall=overall, dimensions=dims, rationale=rationale, policy_gate=policy_gate)
