from app.rules.dsl import ChangeIntent
from app.rules.resolver import RuleResolver


def _rules():
    return [
        {
            "id": "1",
            "rule_id": "RULE-UNIV-DISCLAIMER-001",
            "name": "Universal",
            "status": "ACTIVE",
            "priority": 100,
            "rule_category": "DISCLAIMER",
            "scope_type": "UNIVERSAL",
            "market": None,
            "brand": None,
            "therapeutic_area": None,
            "material_type": None,
        },
        {
            "id": "2",
            "rule_id": "RULE-US-CV-002",
            "name": "US CV",
            "status": "ACTIVE",
            "priority": 80,
            "rule_category": "DISCLAIMER",
            "scope_type": "MARKET",
            "market": "US",
            "brand": None,
            "therapeutic_area": "Cardiovascular",
            "material_type": "Promotional",
        },
        {
            "id": "3",
            "rule_id": "RULE-US-DRUGA-CV-014",
            "name": "US Drug A CV",
            "status": "ACTIVE",
            "priority": 10,
            "rule_category": "DISCLAIMER",
            "scope_type": "MARKET_BRAND",
            "market": "US",
            "brand": "Drug A",
            "therapeutic_area": "Cardiovascular",
            "material_type": "Promotional",
        },
    ]


def test_market_brand_overrides_market_and_universal():
    intent = ChangeIntent(
        change_type="TEXT_STRING_UPDATE",
        intent="UPDATE_DISCLAIMER",
        market={"value": "US", "confidence": 0.99},
        brand={"value": "Drug A", "confidence": 0.99},
        therapeutic_area={"value": "Cardiovascular", "confidence": 0.97},
        material_type={"value": "Promotional", "confidence": 0.8},
        rule_category={"value": "DISCLAIMER", "confidence": 0.9},
    )
    result = RuleResolver().resolve(intent, _rules())
    assert result.selected is not None
    assert result.selected.rule_id == "RULE-US-DRUGA-CV-014"
    assert "RULE-US-CV-002" in result.overridden_rule_ids
    assert "Universal" in result.hierarchy_path
    assert "United States" in result.hierarchy_path or "US" in result.hierarchy_path


def test_market_selected_when_brand_does_not_match():
    intent = ChangeIntent(
        change_type="TEXT_STRING_UPDATE",
        intent="UPDATE_DISCLAIMER",
        market={"value": "US", "confidence": 0.99},
        brand={"value": "Drug B", "confidence": 0.99},
        therapeutic_area={"value": "Cardiovascular", "confidence": 0.97},
        rule_category={"value": "DISCLAIMER", "confidence": 0.9},
        material_type={"value": "Promotional", "confidence": 0.8},
    )
    result = RuleResolver().resolve(intent, _rules())
    assert result.selected.rule_id == "RULE-US-CV-002"
