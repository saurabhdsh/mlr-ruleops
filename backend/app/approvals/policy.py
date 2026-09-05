from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.enums import RoleName


@dataclass
class PolicyMatch:
    policy_name: str
    required_roles: list[str]
    governance_label: str
    reason: str


class ApprovalPolicyEngine:
    """Deterministic approval routing. Governance labels are configurable, not vendor-specific."""

    DEFAULT_POLICIES = [
        {
            "name": "scientific_accuracy",
            "when": {"category_in": ["SCIENTIFIC_ACCURACY", "CITATION"]},
            "roles": [RoleName.MEDICAL_REVIEWER.value, RoleName.MLR_ADMIN.value],
            "governance_label": "Scientific accuracy dual control",
            "priority": 10,
        },
        {
            "name": "universal_scope",
            "when": {"scope_type": "UNIVERSAL"},
            "roles": [RoleName.MLR_ADMIN.value, RoleName.REGULATORY_REVIEWER.value, RoleName.ADMIN.value],
            "governance_label": "Enterprise rule governance board",
            "priority": 20,
        },
        {
            "name": "critical_risk",
            "when": {"risk": "CRITICAL"},
            "roles": [
                RoleName.MEDICAL_REVIEWER.value,
                RoleName.REGULATORY_REVIEWER.value,
                RoleName.MLR_ADMIN.value,
            ],
            "governance_label": "Critical risk multi-party approval",
            "priority": 5,
        },
        {
            "name": "high_risk",
            "when": {"risk": "HIGH"},
            "roles": [RoleName.MLR_ADMIN.value],
            "governance_label": "High risk MLR administration",
            "priority": 30,
        },
        {
            "name": "standard",
            "when": {},
            "roles": [RoleName.MLR_ADMIN.value],
            "governance_label": "Standard MLR change approval",
            "priority": 100,
        },
    ]

    def __init__(self, policies: list[dict[str, Any]] | None = None) -> None:
        self.policies = policies or self.DEFAULT_POLICIES

    def resolve(
        self,
        *,
        category: str | None,
        scope_type: str | None,
        risk: str,
        citation_unverified: bool = False,
        hitl_gate: str | None = None,
    ) -> PolicyMatch:
        if citation_unverified:
            return PolicyMatch(
                policy_name="citation_block",
                required_roles=[],
                governance_label="Deployment blocked pending citation verification",
                reason="Unresolved scientific citation",
            )
        if hitl_gate == "Gate1-IntentConfirm":
            return PolicyMatch(
                policy_name="hitl_gate1",
                required_roles=[],
                governance_label="Gate1-IntentConfirm",
                reason="Insufficient intent — human must confirm market, brand, and change before targeting.",
            )
        if hitl_gate == "Gate2-RuleMatch":
            return PolicyMatch(
                policy_name="hitl_gate2",
                required_roles=[RoleName.MLR_ADMIN.value],
                governance_label="Gate2-RuleMatch",
                reason="Ambiguous rule match — human must confirm the target configuration.",
            )
        if hitl_gate == "Gate3-DualApproval":
            return PolicyMatch(
                policy_name="hitl_gate3_dual",
                required_roles=[RoleName.MEDICAL_REVIEWER.value, RoleName.MLR_ADMIN.value],
                governance_label="Gate3-DualApproval",
                reason="Workbook dual-control gate.",
            )
        if hitl_gate == "Gate3-Block/RMCB":
            return PolicyMatch(
                policy_name="hitl_gate3_block",
                required_roles=[
                    RoleName.MEDICAL_REVIEWER.value,
                    RoleName.REGULATORY_REVIEWER.value,
                    RoleName.MLR_ADMIN.value,
                ],
                governance_label="Gate3-Block/RMCB",
                reason="Guardrail / RMCB block — deploy withheld until the board clears the change.",
            )
        if hitl_gate == "Gate3-SingleApproval":
            return PolicyMatch(
                policy_name="hitl_gate3_single",
                required_roles=[RoleName.MLR_ADMIN.value],
                governance_label="Gate3-SingleApproval",
                reason="Workbook single-approver gate.",
            )
        matches: list[tuple[int, dict]] = []
        for policy in self.policies:
            when = policy.get("when") or {}
            ok = True
            if "risk" in when and when["risk"] != risk:
                ok = False
            if "scope_type" in when and when["scope_type"] != scope_type:
                ok = False
            if "category_in" in when and (category or "") not in when["category_in"]:
                ok = False
            if ok:
                matches.append((policy.get("priority", 100), policy))
        matches.sort(key=lambda x: x[0])
        chosen = matches[0][1] if matches else self.DEFAULT_POLICIES[-1]
        return PolicyMatch(
            policy_name=chosen["name"],
            required_roles=list(chosen["roles"]),
            governance_label=chosen.get("governance_label", ""),
            reason=f"Matched policy {chosen['name']}",
        )

    def is_satisfied(self, required_roles: list[str], decided_roles: list[str]) -> bool:
        needed = set(required_roles)
        have = set(decided_roles)
        if RoleName.ADMIN.value in have:
            return True
        return needed.issubset(have)
