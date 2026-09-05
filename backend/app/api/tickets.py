from __future__ import annotations

import json

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.api.deps import DbDep, UserDep
from app.core.enums import RoleName
from app.core.errors import RuleOpsError
from app.models.approval import ApprovalDecision, ApprovalRequest
from app.models.audit import AuditEvent, WorkflowEvent
from app.models.rule import ChangeOperation, ChangeProposal, RuleDefinition, RuleDependency, RuleVersion
from app.models.ticket import Ticket, TicketAnalysis, TicketAttachment, TicketComment
from app.models.validation import ImpactAnalysis, RiskAssessment, TestResult, TestRun, ValidationResult, ValidationRun
from app.schemas.tickets import ClarifyRequest, TicketCreate, TicketOut
from app.security.auth import require_roles
from app.services.ticket_service import add_comment, clarify_ticket, create_ticket
from app.workflow.orchestrator import TicketOrchestrator

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=list[TicketOut])
def list_tickets(
    db: DbDep,
    user: UserDep,
    status: str | None = None,
    source: str | None = None,
    market: str | None = None,
    brand: str | None = None,
    risk: str | None = None,
    change_type: str | None = None,
    q: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> list[Ticket]:
    query = db.query(Ticket)
    if status:
        query = query.filter(Ticket.status == status)
    if source:
        query = query.filter(Ticket.source_system == source)
    if market:
        query = query.filter(Ticket.market_hint == market)
    if brand:
        query = query.filter(Ticket.brand_hint == brand)
    if risk:
        query = query.filter(Ticket.risk_level == risk)
    if change_type:
        query = query.filter(Ticket.change_type == change_type)
    if q:
        like = f"%{q}%"
        query = query.filter((Ticket.title.ilike(like)) | (Ticket.ticket_number.ilike(like)) | (Ticket.description.ilike(like)))
    return query.order_by(Ticket.created_at.desc()).offset(offset).limit(limit).all()


@router.post("", response_model=TicketOut)
def create(payload: TicketCreate, db: DbDep, user: UserDep) -> Ticket:
    return create_ticket(db, payload.model_dump(), actor_id=user.id)


@router.get("/{ticket_id}")
def get_ticket(ticket_id: str, db: DbDep, user: UserDep) -> dict:
    ticket = _load_ticket(db, ticket_id)
    return serialize_ticket_workspace(db, ticket)


@router.post("/{ticket_id}/process")
def process_ticket(ticket_id: str, db: DbDep, user: UserDep) -> dict:
    ticket = _load_ticket(db, ticket_id)
    from app.workflow.jobs import enqueue_ticket_process

    ran = enqueue_ticket_process(ticket.id)
    if not ran:
        TicketOrchestrator(db).process(ticket.id, actor_id=user.id)
        db.flush()
    db.expire_all()
    ticket = _load_ticket(db, ticket_id)
    workspace = serialize_ticket_workspace(db, ticket)
    workspace["execution"] = {"mode": "celery_worker" if ran else "inline_orchestrator"}
    return workspace


@router.post("/{ticket_id}/clarify")
def clarify(ticket_id: str, payload: ClarifyRequest, db: DbDep, user: UserDep) -> TicketOut:
    ticket = _load_ticket(db, ticket_id)
    if payload.market:
        ticket.market_hint = payload.market
    if payload.brand:
        ticket.brand_hint = payload.brand
    clarify_ticket(db, ticket.id, payload.note, user.id)
    return ticket


@router.post("/{ticket_id}/comments")
def comment(ticket_id: str, payload: ClarifyRequest, db: DbDep, user: UserDep) -> dict:
    c = add_comment(db, _load_ticket(db, ticket_id).id, payload.note, user.id)
    return {"id": c.id, "body": c.body}


def _load_ticket(db: Session, ticket_id: str) -> Ticket:
    ticket = (
        db.query(Ticket)
        .filter((Ticket.id == ticket_id) | (Ticket.ticket_number == ticket_id))
        .one_or_none()
    )
    if ticket is None:
        raise RuleOpsError("TICKET_NOT_FOUND", "Ticket not found", {"id": ticket_id}, False, 404)
    return ticket


def serialize_ticket_workspace(db: Session, ticket: Ticket) -> dict:
    attachments = db.query(TicketAttachment).filter(TicketAttachment.ticket_id == ticket.id).all()
    comments = db.query(TicketComment).filter(TicketComment.ticket_id == ticket.id).all()
    analyses = (
        db.query(TicketAnalysis)
        .filter(TicketAnalysis.ticket_id == ticket.id)
        .order_by(TicketAnalysis.created_at.desc())
        .all()
    )
    analysis = analyses[0] if analyses else None
    proposal = None
    if ticket.current_proposal_id:
        proposal = db.get(ChangeProposal, ticket.current_proposal_id)
    ops = []
    rule = None
    versions = []
    if proposal:
        ops = db.query(ChangeOperation).filter(ChangeOperation.proposal_id == proposal.id).all()
        rule = db.get(RuleDefinition, proposal.target_rule_id)
        versions = (
            db.query(RuleVersion)
            .filter(RuleVersion.rule_id == proposal.target_rule_id)
            .order_by(RuleVersion.version_number.asc())
            .all()
        )
    validation = None
    testrun = None
    impact = None
    risk = None
    approval = None
    if proposal:
        validation = (
            db.query(ValidationRun)
            .filter(ValidationRun.proposal_id == proposal.id)
            .order_by(ValidationRun.created_at.desc())
            .first()
        )
        testrun = (
            db.query(TestRun)
            .filter(TestRun.proposal_id == proposal.id)
            .order_by(TestRun.created_at.desc())
            .first()
        )
        impact = (
            db.query(ImpactAnalysis)
            .filter(ImpactAnalysis.proposal_id == proposal.id)
            .order_by(ImpactAnalysis.created_at.desc())
            .first()
        )
        risk = (
            db.query(RiskAssessment)
            .filter(RiskAssessment.proposal_id == proposal.id)
            .order_by(RiskAssessment.created_at.desc())
            .first()
        )
        approval = (
            db.query(ApprovalRequest)
            .filter(ApprovalRequest.proposal_id == proposal.id)
            .order_by(ApprovalRequest.created_at.desc())
            .first()
        )
    vresults = (
        db.query(ValidationResult).filter(ValidationResult.run_id == validation.id).all() if validation else []
    )
    tresults = (
        db.query(TestResult).filter(TestResult.run_id == testrun.id).limit(80).all() if testrun else []
    )
    decisions = (
        db.query(ApprovalDecision).filter(ApprovalDecision.request_id == approval.id).all() if approval else []
    )
    events = (
        db.query(WorkflowEvent)
        .filter(WorkflowEvent.ticket_id == ticket.id)
        .order_by(WorkflowEvent.sequence.asc())
        .all()
    )
    audit = (
        db.query(AuditEvent)
        .filter(AuditEvent.ticket_id == ticket.id)
        .order_by(AuditEvent.timestamp.asc())
        .all()
    )
    deps = []
    if rule:
        deps = db.query(RuleDependency).filter(RuleDependency.rule_id == rule.id).all()

    interpretation = None
    if analysis:
        interpretation = {
            "id": analysis.id,
            "provider_name": analysis.provider_name,
            "model_name": analysis.model_name,
            "is_local_fallback": analysis.is_local_fallback,
            "mode_label": "Local deterministic interpretation mode"
            if analysis.is_local_fallback
            else f"{analysis.provider_name} / {analysis.model_name}",
            "prompt_template_version": analysis.prompt_template_version,
            "output_schema_version": analysis.output_schema_version,
            "structured_output": json.loads(analysis.structured_output),
            "decision_summary": analysis.decision_summary,
            "overall_confidence": analysis.overall_confidence,
            "sources_used": json.loads(analysis.sources_used or "[]"),
            "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
            "entities": [
                {"field_name": e.field_name, "value": e.value, "confidence": e.confidence}
                for e in analysis.entities
            ],
        }

    return {
        "ticket": TicketOut.model_validate(ticket).model_dump(),
        "attachments": [{"id": a.id, "filename": a.filename, "content": a.content} for a in attachments],
        "comments": [{"id": c.id, "body": c.body, "author_type": c.author_type, "created_at": c.created_at} for c in comments],
        "interpretation": interpretation,
        "proposal": _ser_proposal(proposal, ops, rule, versions) if proposal else None,
        "validation": {
            "id": validation.id,
            "overall_status": validation.overall_status,
            "summary": validation.summary,
            "results": [
                {
                    "validator_name": r.validator_name,
                    "status": r.status,
                    "severity": r.severity,
                    "message": r.message,
                    "evidence": json.loads(r.evidence or "{}"),
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                }
                for r in vresults
            ],
        }
        if validation
        else None,
        "test_run": {
            "id": testrun.id,
            "status": testrun.status,
            "total_cases": testrun.total_cases,
            "unchanged_cases": testrun.unchanged_cases,
            "intentionally_changed_cases": testrun.intentionally_changed_cases,
            "unexpected_changed_cases": testrun.unexpected_changed_cases,
            "new_false_positives": testrun.new_false_positives,
            "new_false_negatives": testrun.new_false_negatives,
            "baseline_flag_rate": testrun.baseline_flag_rate,
            "proposed_flag_rate": testrun.proposed_flag_rate,
            "flag_rate_delta": testrun.flag_rate_delta,
            "duration_ms": testrun.duration_ms,
            "regression_safety": testrun.regression_safety,
            "results": [
                {
                    "review_id": r.review_id,
                    "classification": r.classification,
                    "baseline_flags": json.loads(r.baseline_flags or "[]"),
                    "proposed_flags": json.loads(r.proposed_flags or "[]"),
                    "notes": r.notes,
                }
                for r in tresults
            ],
        }
        if testrun
        else None,
        "impact": json.loads(impact.summary_json) if impact else None,
        "risk": {
            "overall": risk.overall_level,
            "dimensions": json.loads(risk.dimensions_json),
            "rationale": risk.rationale,
            "policy_gate": risk.policy_gate,
            "ai_summary": risk.ai_summary,
        }
        if risk
        else None,
        "approval": {
            "id": approval.id,
            "status": approval.status,
            "required_roles": json.loads(approval.required_roles or "[]"),
            "risk_level_at_request": approval.risk_level_at_request,
            "decisions": [
                {
                    "id": d.id,
                    "approver_id": d.approver_id,
                    "approver_role": d.approver_role,
                    "decision": d.decision,
                    "comment": d.comment,
                    "timestamp": d.timestamp.isoformat(),
                    "risk_score_at_approval": d.risk_score_at_approval,
                }
                for d in decisions
            ],
        }
        if approval
        else None,
        "workflow_events": [
            {
                "id": e.id,
                "sequence": e.sequence,
                "event_type": e.event_type,
                "message": e.message,
                "timestamp": e.timestamp.isoformat(),
                "payload": json.loads(e.payload or "{}"),
            }
            for e in events
        ],
        "audit": [
            {
                "id": a.id,
                "event_type": a.event_type,
                "entity_type": a.entity_type,
                "actor_type": a.actor_type,
                "timestamp": a.timestamp.isoformat(),
                "checksum": a.checksum,
            }
            for a in audit
        ],
        "dependencies": [{"id": d.id, "depends_on_rule_id": d.depends_on_rule_id, "notes": d.notes} for d in deps],
        "matrix": _ser_matrix(events),
        "llm_mode": interpretation["mode_label"] if interpretation else None,
    }


def _ser_matrix(events) -> dict:
    import json as _json

    latest = None
    for event in reversed(events):
        if event.event_type in {"MATRIX_MATCHED", "MATRIX_AMBIGUOUS", "MATRIX_MISS"}:
            latest = event
            break
    if latest is None:
        return {"status": None, "selected": None, "candidates": []}
    payload = _json.loads(latest.payload or "{}")
    return {
        "status": latest.event_type,
        "message": latest.message,
        "selected": payload.get("selected"),
        "candidates": payload.get("candidates") or [],
    }


def _ser_proposal(proposal, ops, rule, versions):
    import json as _json

    current = None
    if proposal:
        base = next((v for v in versions if v.id == proposal.base_rule_version_id), None)
        current = _json.loads(base.body_json) if base else None
    return {
        "id": proposal.id,
        "status": proposal.status,
        "reason": proposal.reason,
        "is_stale": proposal.is_stale,
        "target_rule_id": rule.rule_id if rule else None,
        "target_rule_pk": proposal.target_rule_id,
        "base_rule_version_id": proposal.base_rule_version_id,
        "proposed_checksum": proposal.proposed_checksum,
        "proposed_body": _json.loads(proposal.proposed_body_json),
        "current_body": current,
        "semantic_diff": _json.loads(proposal.semantic_diff_json or "{}"),
        "decision_record": proposal.decision_record,
        "provider_name": proposal.provider_name,
        "model_name": proposal.model_name,
        "prompt_template_version": proposal.prompt_template_version,
        "output_schema_version": proposal.output_schema_version,
        "sources_used": _json.loads(proposal.sources_used or "[]"),
        "operations": [{"operation": o.operation, "value": o.value, "path": o.path} for o in ops],
        "versions": [
            {
                "id": v.id,
                "version_label": v.version_label,
                "is_production": v.is_production,
                "checksum_sha256": v.checksum_sha256,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
    }
