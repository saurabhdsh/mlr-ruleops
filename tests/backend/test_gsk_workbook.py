from app.approvals.policy import ApprovalPolicyEngine
from app.core.enums import HitlGate
from app.models.rule import RuleDefinition
from app.models.ticket import Ticket


def test_workbook_tickets_sit_on_top_of_exam_seed(db):
    exam = db.query(Ticket).filter(Ticket.ticket_number == "TKT-1001").one()
    assert exam.hitl_gate == HitlGate.GATE3_SINGLE_APPROVAL.value
    workbook = (
        db.query(Ticket)
        .filter(Ticket.ticket_number.like("TCK-%"))
        .order_by(Ticket.ticket_number)
        .all()
    )
    assert len(workbook) == 16
    assert [t.ticket_number for t in workbook] == [f"TCK-{n}" for n in range(1001, 1017)]
    gates = {t.ticket_number: t.hitl_gate for t in workbook}
    assert gates["TCK-1001"] == "Gate3-SingleApproval"
    assert gates["TCK-1004"] == "Gate2-RuleMatch"
    assert gates["TCK-1005"] == "Gate3-DualApproval"
    assert gates["TCK-1009"] == "Gate3-Block/RMCB"
    assert gates["TCK-1012"] == "Gate1-IntentConfirm"
    assert gates["TCK-1014"] == "Gate3-Block/RMCB"
    assert gates["TCK-1016"] == "Gate3-SingleApproval"


def test_workbook_target_rules_exist(db):
    ids = {
        "MB-US-TRE-001",
        "MB-US-TRE-000",
        "MKT-US-002",
        "MB-DE-TRE-001",
        "BRD-TRE-001",
        "MB-US-JEM-001",
        "SCI-003",
        "MB-JP-JEM-001",
        "UNI-001",
        "BRD-JEM-001",
        "MB-BR-NUC-001",
        "MB-US-BLE-001",
        "MB-UK-SHI-001",
        "MKT-LATAM-001",
        "MB-FR-BEN-001",
    }
    have = {r.rule_id for r in db.query(RuleDefinition).filter(RuleDefinition.rule_id.in_(ids)).all()}
    assert have == ids


def test_hitl_policy_routing():
    single = ApprovalPolicyEngine().resolve(
        category="DISCLAIMER", scope_type="MARKET_BRAND", risk="LOW", hitl_gate="Gate3-SingleApproval"
    )
    assert single.required_roles == ["MLR_ADMIN"]
    dual = ApprovalPolicyEngine().resolve(
        category="CLAIM", scope_type="MARKET_BRAND", risk="CRITICAL", hitl_gate="Gate3-DualApproval"
    )
    assert set(dual.required_roles) == {"MEDICAL_REVIEWER", "MLR_ADMIN"}
    block = ApprovalPolicyEngine().resolve(
        category="DISCLAIMER", scope_type="MARKET_BRAND", risk="HIGH", hitl_gate="Gate3-Block/RMCB"
    )
    assert "REGULATORY_REVIEWER" in block.required_roles


def test_gate1_ticket_stops_for_intent(client, auth_headers):
    listed = client.get("/api/v1/tickets?q=TCK-1012", headers=auth_headers)
    ticket = next(t for t in listed.json() if t["ticket_number"] == "TCK-1012")
    assert ticket["hitl_gate"] == "Gate1-IntentConfirm"
    processed = client.post(f"/api/v1/tickets/{ticket['id']}/process", headers=auth_headers)
    assert processed.status_code == 200, processed.text
    body = processed.json()
    assert body["ticket"]["status"] == "NEEDS_CLARIFICATION"
    assert body["ticket"]["hitl_gate"] == "Gate1-IntentConfirm"
