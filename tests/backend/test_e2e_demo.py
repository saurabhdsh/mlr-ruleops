from app.models.rule import RuleDefinition, RuleVersion
from app.models.ticket import Ticket


def test_login_and_me(client):
    bad = client.post("/api/v1/auth/login", json={"email": "x@y.com", "password": "no"})
    assert bad.status_code == 401
    ok = client.post(
        "/api/v1/auth/login",
        json={"email": "mlr.admin@mlr-ruleops.local", "password": "ChangeMe!Mlr1"},
    )
    assert ok.status_code == 200
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ok.json()['access_token']}"})
    assert me.json()["email"] == "mlr.admin@mlr-ruleops.local"


def test_full_demo_journey(client, auth_headers, db):
    listed = client.get("/api/v1/tickets", headers=auth_headers)
    assert listed.status_code == 200
    assert any(t["ticket_number"] == "TKT-1001" for t in listed.json())

    created = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={
            "title": "US Cardiovascular Disclaimer Citation Update",
            "description": (
                "Update the US cardiovascular disclaimer for Drug A to include the new 2026 "
                "clinical trial citation and remove reference to the 2020 study."
            ),
            "market_hint": "US",
            "brand_hint": "Drug A",
            "external_id": "E2E-CV-001",
        },
    )
    assert created.status_code == 200
    ticket_id = created.json()["id"]

    # idempotency
    again = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={
            "title": "dup",
            "description": "dup",
            "external_id": "E2E-CV-001",
        },
    )
    assert again.json()["id"] == ticket_id

    processed = client.post(f"/api/v1/tickets/{ticket_id}/process", headers=auth_headers)
    assert processed.status_code == 200, processed.text
    body = processed.json()
    assert body["interpretation"]["is_local_fallback"] is True
    assert "Local deterministic" in body["interpretation"]["mode_label"]
    assert body["matrix"]["status"] == "MATRIX_MATCHED"
    assert body["matrix"]["selected"]["config_id"] == "CFG-US-DRUGA-CV-DISCLAIMER-EN"
    assert body["proposal"]["target_rule_id"] == "RULE-US-DRUGA-CV-014"
    assert "CIT-2026-004" in str(body["proposal"]["proposed_body"])
    assert "CIT-2020-001" not in [r.get("id") for r in body["proposal"]["proposed_body"].get("references", [])]
    assert body["validation"]["overall_status"] == "PASS"
    assert body["test_run"]["total_cases"] > 0
    assert body["test_run"]["regression_safety"] in {"PASS", "FAIL"}
    assert body["impact"]["modified_rules"] == 1
    assert body["risk"]["overall"]
    assert body["approval"]["id"]
    assert body["ticket"]["status"] == "AWAITING_APPROVAL"

    rule = db.query(RuleDefinition).filter(RuleDefinition.rule_id == "RULE-US-DRUGA-CV-014").one()
    before = rule.production_version_id

    approved = client.post(
        f"/api/v1/approvals/{body['approval']['id']}/approve",
        headers=auth_headers,
        json={"comment": "Approved for controlled deployment", "deploy": True},
    )
    assert approved.status_code == 200, approved.text
    after_body = approved.json()
    assert after_body["ticket"]["status"] in {"DEPLOYED", "CLOSED"}

    db.expire_all()
    rule = db.query(RuleDefinition).filter(RuleDefinition.rule_id == "RULE-US-DRUGA-CV-014").one()
    assert rule.production_version_id != before
    new_ver = db.get(RuleVersion, rule.production_version_id)
    assert new_ver.checksum_sha256
    assert "CIT-2026-004" in new_ver.body_json

    audit = client.get("/api/v1/audit", headers=auth_headers)
    types = {e["event_type"] for e in audit.json()}
    assert "CHANGE_PROPOSAL_CREATED" in types or "VERSION_ACTIVATED" in types

    deployments = client.get("/api/v1/deployments", headers=auth_headers).json()
    assert deployments
    dep_id = deployments[0]["id"]
    rollback = client.post(
        f"/api/v1/deployments/{dep_id}/rollback",
        headers=auth_headers,
        json={"target_version_id": before, "reason": "E2E rollback verification", "rule_id": rule.id},
    )
    assert rollback.status_code == 200, rollback.text
    db.expire_all()
    rule = db.query(RuleDefinition).filter(RuleDefinition.rule_id == "RULE-US-DRUGA-CV-014").one()
    assert rule.production_version_id == before


def test_stale_proposal_prevention(client, auth_headers, db):
    from app.core.errors import StaleBaseVersion
    from app.deployment.engine import DeploymentEngine
    from app.models.user import User
    from app.services.governance import deploy_proposal

    ticket = client.post(
        "/api/v1/tickets",
        headers=auth_headers,
        json={
            "title": "US Cardiovascular Disclaimer Citation Update",
            "description": "Update the US cardiovascular disclaimer for Drug A to include the new 2026 clinical trial citation and remove reference to the 2020 study.",
            "external_id": "E2E-STALE-001",
            "market_hint": "US",
            "brand_hint": "Drug A",
        },
    ).json()
    processed = client.post(f"/api/v1/tickets/{ticket['id']}/process", headers=auth_headers).json()
    proposal_id = processed["proposal"]["id"]
    rule = db.query(RuleDefinition).filter(RuleDefinition.rule_id == "RULE-US-DRUGA-CV-014").one()
    # Move production pointer to simulate concurrent deploy
    other = (
        db.query(RuleVersion)
        .filter(RuleVersion.rule_id == rule.id, RuleVersion.id != rule.production_version_id)
        .first()
    )
    if other:
        rule.production_version_id = other.id
        db.commit()
    user = db.query(User).filter(User.email == "mlr.admin@mlr-ruleops.local").one()
    # Force approved state
    from app.models.rule import ChangeProposal
    from app.models.ticket import Ticket as T

    p = db.get(ChangeProposal, proposal_id)
    p.status = "APPROVED"
    t = db.get(T, ticket["id"])
    t.status = "APPROVED"
    db.commit()
    try:
        deploy_proposal(db, proposal_id, user)
        assert False, "expected stale"
    except StaleBaseVersion:
        pass


def test_webhook_and_integrations(client, auth_headers):
    resp = client.post(
        "/api/v1/integrations/webhook/ticket",
        json={
            "external_id": "WH-1",
            "title": "Webhook ticket",
            "description": "From internal webhook",
            "source_system": "WEBHOOK",
        },
    )
    assert resp.status_code == 200
    ints = client.get("/api/v1/integrations", headers=auth_headers).json()
    snow = next(i for i in ints if i["provider"] == "servicenow")
    assert snow["status"] == "NOT_CONFIGURED"


def test_analytics_from_db(client, auth_headers):
    data = client.get("/api/v1/analytics/dashboard", headers=auth_headers).json()
    assert data["total_tickets"] >= 10
    assert data["dataset_label"] == "Synthetic Demo Data"
    assert "open_tickets" in data


def test_health():
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    assert c.get("/api/v1/health").json()["status"] == "ok"


def test_rule_execute_uses_production_body(client, auth_headers):
    probe = {
        "rule_id": "RULE-US-DRUGA-CV-014",
        "market": "US",
        "brand": "Drug A",
        "therapeutic_area": "Cardiovascular",
        "material_type": "Promotional",
        "language": "EN",
        "content": "Drug A cardiovascular promotional material citing CIT-2020-001 from 2020.",
    }
    resp = client.post("/api/v1/rules/execute", headers=auth_headers, json=probe)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["rules_evaluated"] == 1
    assert "RULE-US-DRUGA-CV-014" in data["matched_rule_ids"]
    assert any("CIT-2020-001" in f for f in data["flags"])
