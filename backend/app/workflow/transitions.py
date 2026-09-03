from app.core.enums import ALLOWED_TRANSITIONS, WorkflowState
from app.core.errors import IllegalTransition
from app.models.ticket import Ticket


def transition(ticket: Ticket, target: WorkflowState) -> None:
    current = WorkflowState(ticket.status)
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise IllegalTransition(current.value, target.value)
    ticket.status = target.value
