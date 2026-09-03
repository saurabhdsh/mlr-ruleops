from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.approvals.policy import ApprovalPolicyEngine
from app.audit.ledger import AuditLedger
from app.core.enums import ActorType, ApprovalDecisionType, RoleName, WorkflowState
from app.core.errors import ApprovalRequired, DeploymentFailed, ForbiddenAction, StaleBaseVersion, ValidationFailed
from app.deployment.engine import DeploymentEngine
from app.models.approval import ApprovalDecision, ApprovalRequest
from app.models.deployment import Deployment, RollbackEvent
from app.models.rule import ChangeProposal, RuleDefinition, RuleVersion
from app.models.ticket import Ticket
from app.models.user import User
from app.models.validation import RiskAssessment
from app.rules.checksum import rule_checksum
from app.rules.dsl import parse_rule_body
from app.workflow.events import publish_ticket_event
from app.workflow.transitions import transition


def _emit(db: Session, ticket: Ticket, event_type: str, message: str, payload: dict | None = None) -> None:
    AuditLedger(db).workflow(ticket.id, event_type, message, payload)
    publish_ticket_event(ticket.id, {"event_type": event_type, "message": message, "payload": payload or {}})


def decide_approval(
    db: Session,
    request_id: str,
    user: User,
    decision: str,
    comment: str,
    deploy: bool = False,
) -> ApprovalRequest:
    req = db.get(ApprovalRequest, request_id)
    if req is None:
        raise ValidationFailed("Approval request not found")
    proposal = db.get(ChangeProposal, req.proposal_id)
    ticket = db.get(Ticket, req.ticket_id)
    if proposal is None or ticket is None:
        raise ValidationFailed("Proposal or ticket missing")
    if proposal.approval_invalidated or proposal.is_stale:
        raise StaleBaseVersion("Proposal was modified after a previous approval and must be re-evaluated")
    if proposal.proposed_checksum != req.proposal_checksum:
        proposal.approval_invalidated = True
        raise StaleBaseVersion("Proposal checksum changed; previous approvals are invalid")

    roles = set(user.role_names())
    required = set(json.loads(req.required_roles or "[]"))
    acting_role = next((r for r in roles if r in required), None)
    if RoleName.ADMIN.value in roles:
        acting_role = RoleName.ADMIN.value
    if decision in {ApprovalDecisionType.APPROVE, ApprovalDecisionType.APPROVE_AND_DEPLOY} and not acting_role:
        if not roles.intersection(required | {RoleName.MLR_ADMIN.value, RoleName.ADMIN.value}):
            raise ForbiddenAction("Your role cannot approve this change")
        acting_role = next(iter(roles.intersection({RoleName.MLR_ADMIN.value, RoleName.ADMIN.value})), next(iter(roles)))

    if decision in {ApprovalDecisionType.REJECT, ApprovalDecisionType.REQUEST_CHANGES} and not comment.strip():
        raise ValidationFailed("A comment is required for this decision")

    risk = (
        db.query(RiskAssessment)
        .filter(RiskAssessment.proposal_id == proposal.id)
        .order_by(RiskAssessment.created_at.desc())
        .first()
    )
    dec = ApprovalDecision(
        request_id=req.id,
        approver_id=user.id,
        approver_role=acting_role or next(iter(roles), "VIEWER"),
        decision=decision,
        comment=comment,
        proposal_id=proposal.id,
        rule_version_id=proposal.base_rule_version_id,
        risk_score_at_approval=risk.overall_level if risk else "UNKNOWN",
        timestamp=datetime.now(UTC),
    )
    db.add(dec)
    db.flush()
    AuditLedger(db).record(
        event_type="APPROVAL_DECISION",
        entity_type="approval_decision",
        entity_id=dec.id,
        actor_type=ActorType.USER,
        actor_id=user.id,
        ticket_id=ticket.id,
        new_state={"decision": decision, "role": dec.approver_role, "risk": dec.risk_score_at_approval},
    )

    if decision == ApprovalDecisionType.REJECT:
        req.status = "REJECTED"
        proposal.status = "REJECTED"
        if ticket.status == WorkflowState.AWAITING_APPROVAL:
            transition(ticket, WorkflowState.REJECTED)
        _emit(db, ticket, "APPROVAL_REJECTED", "Proposal rejected")
        return req
    if decision == ApprovalDecisionType.REQUEST_CHANGES:
        req.status = "CHANGES_REQUESTED"
        if ticket.status == WorkflowState.AWAITING_APPROVAL:
            transition(ticket, WorkflowState.PROPOSING_CHANGE)
        _emit(db, ticket, "CHANGES_REQUESTED", "Changes requested")
        return req
    if decision == ApprovalDecisionType.REQUEST_CLARIFICATION:
        req.status = "CLARIFICATION"
        if ticket.status == WorkflowState.AWAITING_APPROVAL:
            transition(ticket, WorkflowState.NEEDS_CLARIFICATION)
        _emit(db, ticket, "CLARIFICATION_REQUESTED", "Clarification requested")
        return req

    approved_roles = [
        d.approver_role
        for d in req.decisions
        if d.decision in {ApprovalDecisionType.APPROVE, ApprovalDecisionType.APPROVE_AND_DEPLOY}
    ]
    approved_roles.append(dec.approver_role)
    if not ApprovalPolicyEngine().is_satisfied(list(required), approved_roles) and RoleName.ADMIN.value not in roles:
        # MLR_ADMIN may complete HIGH-risk gates when they are an explicitly required role
        if not (
            RoleName.MLR_ADMIN.value in roles
            and RoleName.MLR_ADMIN.value in required
            and risk
            and risk.overall_level in {"LOW", "MEDIUM", "HIGH"}
            and RoleName.REGULATORY_REVIEWER.value not in required
        ):
            req.status = "PENDING"
            _emit(db, ticket, "PARTIAL_APPROVAL", "Additional approvers still required")
            return req

    req.status = "APPROVED"
    proposal.status = "APPROVED"
    if ticket.status == WorkflowState.AWAITING_APPROVAL:
        transition(ticket, WorkflowState.APPROVED)
    _emit(db, ticket, "APPROVAL_GRANTED", "Approval granted")
    AuditLedger(db).record(
        event_type="APPROVAL_GRANTED",
        entity_type="approval_request",
        entity_id=req.id,
        actor_type=ActorType.USER,
        actor_id=user.id,
        ticket_id=ticket.id,
    )
    if deploy or decision == ApprovalDecisionType.APPROVE_AND_DEPLOY:
        deploy_proposal(db, proposal.id, user)
    return req


def deploy_proposal(db: Session, proposal_id: str, user: User) -> Deployment:
    proposal = db.get(ChangeProposal, proposal_id)
    if proposal is None:
        raise DeploymentFailed("Proposal not found")
    ticket = db.get(Ticket, proposal.ticket_id)
    rule = db.get(RuleDefinition, proposal.target_rule_id)
    if ticket is None or rule is None:
        raise DeploymentFailed("Ticket or rule missing")
    if proposal.status not in {"APPROVED", "READY"} and ticket.status not in {
        WorkflowState.APPROVED,
        WorkflowState.AWAITING_APPROVAL,
    }:
        raise ApprovalRequired("Proposal is not approved for deployment")
    if ticket.status == WorkflowState.AWAITING_APPROVAL:
        raise ApprovalRequired("Human approval is still required")

    from app.models.validation import ValidationRun

    latest_val = (
        db.query(ValidationRun)
        .filter(ValidationRun.proposal_id == proposal.id)
        .order_by(ValidationRun.created_at.desc())
        .first()
    )
    if latest_val is None or latest_val.blocking or latest_val.overall_status != "PASS":
        raise ValidationFailed("Proposal has not passed blocking validation")

    engine = DeploymentEngine()
    if rule.production_version_id != proposal.base_rule_version_id:
        proposal.is_stale = True
        raise StaleBaseVersion("Production version no longer matches proposal base version")

    body = json.loads(proposal.proposed_body_json)
    parse_rule_body(body)
    checksum = rule_checksum(body)
    if checksum != proposal.proposed_checksum:
        raise DeploymentFailed("Proposed checksum mismatch")

    if ticket.status == WorkflowState.APPROVED:
        transition(ticket, WorkflowState.DEPLOYING)
    _emit(db, ticket, "DEPLOYMENT_STARTED", "Deployment started")
    AuditLedger(db).record(
        event_type="DEPLOYMENT_STARTED",
        entity_type="proposal",
        entity_id=proposal.id,
        actor_type=ActorType.USER,
        actor_id=user.id,
        ticket_id=ticket.id,
    )

    max_ver = max((v.version_number for v in rule.versions), default=0) if rule.versions else (
        db.query(RuleVersion).filter(RuleVersion.rule_id == rule.id).count()
    )
    # Reload versions
    versions = db.query(RuleVersion).filter(RuleVersion.rule_id == rule.id).all()
    max_ver = max((v.version_number for v in versions), default=0)
    new_ver = RuleVersion(
        rule_id=rule.id,
        version_number=max_ver + 1,
        version_label=f"v{max_ver + 1}",
        body_json=json.dumps(body),
        checksum_sha256=checksum,
        created_by=user.id,
        change_summary=proposal.reason,
        is_production=True,
        parent_version_id=proposal.base_rule_version_id,
    )
    db.add(new_ver)
    db.flush()
    for v in versions:
        v.is_production = False
    new_ver.is_production = True
    from_id = rule.production_version_id
    rule.production_version_id = new_ver.id
    rule.lock_version = (rule.lock_version or 1) + 1

    smoke = engine.smoke_test(body)
    dep = Deployment(
        proposal_id=proposal.id,
        ticket_id=ticket.id,
        rule_id=rule.id,
        from_version_id=from_id or proposal.base_rule_version_id,
        to_version_id=new_ver.id,
        deployed_by=user.id,
        status="SUCCESS" if smoke.status == "PASS" else "FAILED",
        smoke_test_status=smoke.status,
        smoke_test_notes=smoke.notes,
        deployed_at=datetime.now(UTC),
    )
    db.add(dep)
    proposal.status = "DEPLOYED"
    if smoke.status != "PASS":
        if ticket.status == WorkflowState.DEPLOYING:
            transition(ticket, WorkflowState.DEPLOYMENT_FAILED)
        raise DeploymentFailed(smoke.notes)
    if ticket.status == WorkflowState.DEPLOYING:
        transition(ticket, WorkflowState.DEPLOYED)
    _emit(db, ticket, "VERSION_ACTIVATED", f"Version {new_ver.version_label} activated")
    _emit(db, ticket, "SMOKE_TEST_PASSED", smoke.notes)
    AuditLedger(db).record(
        event_type="VERSION_ACTIVATED",
        entity_type="rule_version",
        entity_id=new_ver.id,
        actor_type=ActorType.USER,
        actor_id=user.id,
        ticket_id=ticket.id,
        checksum=checksum,
        new_state={"version": new_ver.version_label, "rule_id": rule.rule_id},
    )
    ticket.status = WorkflowState.CLOSED
    ticket.closed_at = datetime.now(UTC)
    _emit(db, ticket, "TICKET_CLOSED", "Ticket closed after successful deployment")
    return dep


def rollback_rule(
    db: Session,
    rule_id: str,
    target_version_id: str,
    reason: str,
    user: User,
    ticket_id: str | None = None,
) -> RollbackEvent:
    rule = db.query(RuleDefinition).filter(
        (RuleDefinition.id == rule_id) | (RuleDefinition.rule_id == rule_id)
    ).one_or_none()
    if rule is None:
        raise DeploymentFailed("Rule not found")
    target = db.get(RuleVersion, target_version_id)
    if target is None or target.rule_id != rule.id:
        raise DeploymentFailed("Target version does not belong to this rule")
    parse_rule_body(json.loads(target.body_json))
    from_id = rule.production_version_id
    for v in db.query(RuleVersion).filter(RuleVersion.rule_id == rule.id).all():
        v.is_production = False
    target.is_production = True
    rule.production_version_id = target.id
    rule.lock_version = (rule.lock_version or 1) + 1
    smoke = DeploymentEngine().smoke_test(json.loads(target.body_json))
    event = RollbackEvent(
        rule_id=rule.id,
        from_version_id=from_id or target.id,
        to_version_id=target.id,
        reason=reason,
        rolled_back_by=user.id,
        smoke_test_status=smoke.status,
        ticket_id=ticket_id,
    )
    db.add(event)
    if ticket_id:
        ticket = db.get(Ticket, ticket_id)
        if ticket and ticket.status in {WorkflowState.DEPLOYED, WorkflowState.CLOSED}:
            ticket.status = WorkflowState.ROLLED_BACK
            _emit(db, ticket, "ROLLED_BACK", f"Rolled back to {target.version_label}")
    AuditLedger(db).record(
        event_type="ROLLBACK",
        entity_type="rule_version",
        entity_id=target.id,
        actor_type=ActorType.USER,
        actor_id=user.id,
        ticket_id=ticket_id,
        checksum=target.checksum_sha256,
        previous_state={"from": from_id},
        new_state={"to": target.id, "version": target.version_label},
        metadata={"reason": reason},
    )
    return event
