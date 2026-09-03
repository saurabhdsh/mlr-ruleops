from types import SimpleNamespace

from app.ai.fallback import DeterministicFallbackProvider
from app.ai.grounding import ground_intent_citations
from app.rules.dsl import ChangeIntent
from app.audit.ledger import AuditLedger
from app.models.ticket import Ticket


def test_fallback_interprets_demo_ticket():
    intent = DeterministicFallbackProvider().interpret_ticket(
        "US Cardiovascular Disclaimer Citation Update",
        "Update the US cardiovascular disclaimer for Drug A to include the new 2026 clinical trial citation and remove reference to the 2020 study.",
        {},
    )
    assert intent.change_type == "TEXT_STRING_UPDATE"
    assert intent.market.value == "US"
    assert intent.brand.value == "Drug A"
    assert intent.therapeutic_area.value == "Cardiovascular"
    assert intent.citation_to_remove == "CIT-2020-001"
    assert intent.citation_to_add == "CIT-2026-004"
    assert DeterministicFallbackProvider.is_local_fallback is True


def test_audit_event_creation(db):
    ticket = db.query(Ticket).filter(Ticket.ticket_number == "TKT-1001").one()
    event = AuditLedger(db).record(
        event_type="UNIT_TEST",
        entity_type="ticket",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        new_state={"ok": True},
        checksum="abc",
    )
    db.flush()
    assert event.id
    assert event.event_type == "UNIT_TEST"


def test_citation_grounding_resolves_years_to_catalog_ids():
    citations = [
        SimpleNamespace(citation_id="CIT-2020-001", year=2020),
        SimpleNamespace(citation_id="CIT-2026-004", year=2026),
    ]
    intent = ChangeIntent(change_type="TEXT_STRING_UPDATE", intent="UPDATE_DISCLAIMER")
    grounded = ground_intent_citations(
        intent,
        "US Cardiovascular Disclaimer Citation Update",
        "include the new 2026 clinical trial citation and remove reference to the 2020 study",
        citations,
    )
    assert grounded.citation_to_remove == "CIT-2020-001"
    assert grounded.citation_to_add == "CIT-2026-004"
