from app.rules.dsl import MutationOperation, parse_rule_body
from app.rules.mutation import RuleMutationEngine
from app.rules.validators import is_blocking, run_validators


TEXT = {
    "rule_type": "TEXT",
    "rule_id": "RULE-US-DRUGA-CV-014",
    "field": "disclaimer",
    "scope": {"market": "US", "brand": "Drug A"},
    "content": "Supported by 2020 study CIT-2020-001.",
    "references": [{"type": "scientific_citation", "id": "CIT-2020-001"}],
}

LOGIC = {
    "rule_type": "LOGIC",
    "rule_id": "RULE-LOGIC-DRUGX-MY-001",
    "when": {
        "all": [
            {"field": "brand", "operator": "eq", "value": "Drug X"},
            {"field": "market", "operator": "eq", "value": "UK"},
        ]
    },
    "actions": [{"type": "route", "target": "Reviewer A"}, {"type": "flag", "value": "Old"}],
}


def test_text_mutation_swaps_citations():
    result = RuleMutationEngine().apply(
        TEXT,
        [
            MutationOperation(operation="REMOVE_REFERENCE", value="CIT-2020-001"),
            MutationOperation(operation="ADD_REFERENCE", value="CIT-2026-004"),
            MutationOperation(operation="REPLACE_TEXT", value="Supported by 2026 trial CIT-2026-004."),
        ],
    )
    refs = [r["id"] for r in result.proposed_body["references"]]
    assert "CIT-2026-004" in refs
    assert "CIT-2020-001" not in refs
    assert result.diff["added_references"] == ["CIT-2026-004"]
    parse_rule_body(result.proposed_body)


def test_logic_mutation_route_and_flag():
    result = RuleMutationEngine().apply(
        LOGIC,
        [
            {"operation": "CHANGE_ROUTE", "value": "Reviewer Z"},
            {"operation": "REMOVE_FLAG", "value": "Old"},
            {"operation": "ADD_FLAG", "value": "Constraint W"},
        ],
    )
    actions = result.proposed_body["actions"]
    assert any(a.get("type") == "route" and a.get("target") == "Reviewer Z" for a in actions)
    assert any(a.get("value") == "Constraint W" for a in actions)


def test_schema_and_reference_validation():
    ctx = {
        "known_citation_ids": ["CIT-2020-001", "CIT-2026-004"],
        "citation_statuses": {"CIT-2020-001": "SYNTHETIC_DEMO", "CIT-2026-004": "SYNTHETIC_DEMO"},
        "expected_market": "US",
        "dependencies": [],
    }
    results = run_validators(TEXT, ctx)
    assert not is_blocking(results)
    bad = dict(TEXT)
    bad["references"] = [{"type": "scientific_citation", "id": "CIT-UNKNOWN"}]
    results = run_validators(bad, ctx)
    assert is_blocking(results)


def test_semantic_year_mismatch_warns():
    body = dict(TEXT)
    body["content"] = "Supported by 2026 trial CIT-2026-004."
    body["references"] = [{"type": "scientific_citation", "id": "CIT-2020-001"}]
    ctx = {"known_citation_ids": ["CIT-2020-001"], "citation_statuses": {"CIT-2020-001": "SYNTHETIC_DEMO"}}
    results = {r.validator_name: r for r in run_validators(body, ctx)}
    assert results["SemanticConsistencyValidator"].status == "WARN"


def test_semantic_matching_years_pass():
    results = {r.validator_name: r for r in run_validators(TEXT, {"known_citation_ids": ["CIT-2020-001"], "citation_statuses": {"CIT-2020-001": "SYNTHETIC_DEMO"}})}
    assert results["SemanticConsistencyValidator"].status == "PASS"


def test_conflict_duplicate_references_warns_not_blocks_unknown():
    body = dict(TEXT)
    body["references"] = [
        {"type": "scientific_citation", "id": "CIT-2020-001"},
        {"type": "scientific_citation", "id": "CIT-2020-001"},
    ]
    ctx = {"known_citation_ids": ["CIT-2020-001"], "citation_statuses": {"CIT-2020-001": "SYNTHETIC_DEMO"}}
    results = {r.validator_name: r for r in run_validators(body, ctx)}
    assert results["ConflictValidator"].status == "WARN"
    assert not is_blocking(list(results.values()))
