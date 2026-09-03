from fastapi import APIRouter

from app.api.deps import DbDep, UserDep
from app.api.tickets import serialize_ticket_workspace
from app.core.enums import RoleName
from app.core.errors import RuleOpsError
from app.models.rule import ChangeProposal
from app.models.ticket import Ticket
from app.security.auth import require_roles
from app.services.governance import deploy_proposal
from app.workflow.orchestrator import TicketOrchestrator

router = APIRouter(tags=["proposals"])


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: str, db: DbDep, user: UserDep) -> dict:
    proposal = db.get(ChangeProposal, proposal_id)
    if proposal is None:
        raise RuleOpsError("PROPOSAL_NOT_FOUND", "Proposal not found", status_code=404)
    ticket = db.get(Ticket, proposal.ticket_id)
    return serialize_ticket_workspace(db, ticket)


@router.post("/proposals/{proposal_id}/validate")
def revalidate(proposal_id: str, db: DbDep, user: UserDep) -> dict:
    proposal = db.get(ChangeProposal, proposal_id)
    if proposal is None:
        raise RuleOpsError("PROPOSAL_NOT_FOUND", "Proposal not found", status_code=404)
    TicketOrchestrator(db).rerun_validation(proposal_id)
    db.flush()
    ticket = db.get(Ticket, proposal.ticket_id)
    return serialize_ticket_workspace(db, ticket)


@router.post("/proposals/{proposal_id}/test")
def retest(proposal_id: str, db: DbDep, user: UserDep) -> dict:
    proposal = db.get(ChangeProposal, proposal_id)
    if proposal is None:
        raise RuleOpsError("PROPOSAL_NOT_FOUND", "Proposal not found", status_code=404)
    TicketOrchestrator(db).rerun_tests(proposal_id)
    db.flush()
    ticket = db.get(Ticket, proposal.ticket_id)
    return serialize_ticket_workspace(db, ticket)


@router.post("/proposals/{proposal_id}/deploy")
def deploy(proposal_id: str, db: DbDep, user: UserDep) -> dict:
    _ = require_roles(RoleName.ADMIN, RoleName.MLR_ADMIN)
    if not set(user.role_names()).intersection({"ADMIN", "MLR_ADMIN"}):
        from app.core.errors import ForbiddenAction

        raise ForbiddenAction("Deployment requires MLR_ADMIN or ADMIN")
    dep = deploy_proposal(db, proposal_id, user)
    ticket = db.get(Ticket, dep.ticket_id)
    return {"deployment_id": dep.id, "workspace": serialize_ticket_workspace(db, ticket)}
