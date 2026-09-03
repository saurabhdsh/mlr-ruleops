from app.approvals.policy import ApprovalPolicyEngine
from app.risk.engine import RiskEngine
from app.rules.engine import ReviewContext, RuleExecutionEngine
from app.testing_engine.regression import RegressionEngine
from app.testing_engine.sandbox import SandboxSession


LOGIC = {
    "rule_type": "LOGIC",
    "rule_id": "R1",
    "when": {
        "all": [
            {"field": "brand", "operator": "eq", "value": "Drug X"},
            {"field": "market", "operator": "eq", "value": "UK"},
        ]
    },
    "actions": [{"type": "route", "target": "Reviewer Z"}, {"type": "flag", "value": "Constraint W"}],
}


def test_logic_execution():
    engine = RuleExecutionEngine()
    hit = engine.execute_rule(LOGIC, ReviewContext(brand="Drug X", market="UK", content="Drug X"))
    assert hit.route == "Reviewer Z"
    assert "Constraint W" in hit.flags
    miss = engine.execute_rule(LOGIC, ReviewContext(brand="Drug A", market="US"))
    assert miss.route is None


def test_regression_and_fp_calculation():
    production = [
        {
            "rule_type": "TEXT",
            "rule_id": "RULE-US-DRUGA-CV-014",
            "field": "disclaimer",
            "scope": {"market": "US", "brand": "Drug A", "therapeutic_area": "Cardiovascular"},
            "content": "2020 CIT-2020-001",
            "references": [{"type": "scientific_citation", "id": "CIT-2020-001"}],
        }
    ]
    proposed = {
        "rule_type": "TEXT",
        "rule_id": "RULE-US-DRUGA-CV-014",
        "field": "disclaimer",
        "scope": {"market": "US", "brand": "Drug A", "therapeutic_area": "Cardiovascular"},
        "content": "2026 CIT-2026-004",
        "references": [{"type": "scientific_citation", "id": "CIT-2026-004"}],
    }
    reviews = [
        {
            "review_id": "1",
            "market": "US",
            "brand": "Drug A",
            "therapeutic_area": "Cardiovascular",
            "content": "Drug A cardiovascular 2020 study",
            "material_type": "Promotional",
        },
        {
            "review_id": "2",
            "market": "JP",
            "brand": "Drug C",
            "therapeutic_area": "Immunology",
            "content": "unrelated",
            "material_type": "Website",
        },
    ]
    session = SandboxSession(production, proposed, "RULE-US-DRUGA-CV-014")
    report = RegressionEngine().run(
        session,
        reviews,
        {"market": "US", "brand": "Drug A", "therapeutic_area": "Cardiovascular"},
    )
    assert report.total_cases == 2
    assert report.unchanged_cases + report.intentionally_changed_cases + report.unexpected_changed_cases == 2
    assert isinstance(report.flag_rate_delta, float)


def test_risk_and_approval_routing():
    risk = RiskEngine().assess(
        category="DISCLAIMER",
        scope_type="MARKET_BRAND",
        markets=["US"],
        brands=["Drug A"],
        regression_safety="PASS",
        unexpected_changes=0,
        false_positives=0,
        false_negatives=0,
        citation_unverified=False,
        scientific=True,
    )
    assert risk.overall in {"HIGH", "MEDIUM", "CRITICAL"}
    policy = ApprovalPolicyEngine().resolve(
        category="DISCLAIMER",
        scope_type="MARKET_BRAND",
        risk=risk.overall,
    )
    assert "MLR_ADMIN" in policy.required_roles
    assert ApprovalPolicyEngine().is_satisfied(["MLR_ADMIN", "MEDICAL_REVIEWER"], ["MLR_ADMIN", "MEDICAL_REVIEWER"])


def test_critical_risk_requires_three_roles():
    policy = ApprovalPolicyEngine().resolve(category="CLAIM", scope_type="BRAND", risk="CRITICAL")
    assert set(policy.required_roles) >= {"MEDICAL_REVIEWER", "REGULATORY_REVIEWER", "MLR_ADMIN"}
