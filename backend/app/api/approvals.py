from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import DbDep, UserDep
from app.api.tickets import serialize_ticket_workspace
from app.core.enums import ApprovalDecisionType, RoleName
from app.core.errors import RuleOpsError
from app.models.approval import ApprovalRequest
from app.models.ticket import Ticket
from app.services.governance import decide_approval

router = APIRouter(prefix="/approvals", tags=["approvals"])


class DecisionIn(BaseModel):
    comment: str = ""
    deploy: bool = False


@router.get("")
def list_approvals(db: DbDep, user: UserDep, status: str | None = "PENDING") -> list[dict]:
    q = db.query(ApprovalRequest)
    if status:
        q = q.filter(ApprovalRequest.status == status)
    rows = q.order_by(ApprovalRequest.created_at.desc()).limit(100).all()
    out = []
    for r in rows:
        ticket = db.get(Ticket, r.ticket_id)
        out.append(
            {
                "id": r.id,
                "status": r.status,
                "ticket_id": r.ticket_id,
                "ticket_number": ticket.ticket_number if ticket else None,
                "title": ticket.title if ticket else None,
                "risk_level_at_request": r.risk_level_at_request,
                "hitl_gate": ticket.hitl_gate if ticket else None,
                "required_roles": r.required_roles,
                "proposal_id": r.proposal_id,
            }
        )
    return out


@router.post("/{approval_id}/approve")
def approve(approval_id: str, payload: DecisionIn, db: DbDep, user: UserDep) -> dict:
    decision = ApprovalDecisionType.APPROVE_AND_DEPLOY if payload.deploy else ApprovalDecisionType.APPROVE
    req = decide_approval(db, approval_id, user, decision, payload.comment, deploy=payload.deploy)
    ticket = db.get(Ticket, req.ticket_id)
    return serialize_ticket_workspace(db, ticket)


@router.post("/{approval_id}/reject")
def reject(approval_id: str, payload: DecisionIn, db: DbDep, user: UserDep) -> dict:
    req = decide_approval(db, approval_id, user, ApprovalDecisionType.REJECT, payload.comment)
    ticket = db.get(Ticket, req.ticket_id)
    return serialize_ticket_workspace(db, ticket)


@router.post("/{approval_id}/request-change")
def request_change(approval_id: str, payload: DecisionIn, db: DbDep, user: UserDep) -> dict:
    req = decide_approval(db, approval_id, user, ApprovalDecisionType.REQUEST_CHANGES, payload.comment)
    ticket = db.get(Ticket, req.ticket_id)
    return serialize_ticket_workspace(db, ticket)
