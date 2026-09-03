from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.enums import WorkflowState
from app.models.deployment import Deployment, RollbackEvent
from app.models.rule import ChangeProposal, RuleDefinition
from app.models.ticket import Ticket
from app.models.validation import RiskAssessment, TestRun


def dashboard_metrics(db: Session) -> dict:
    open_states = [
        s.value
        for s in WorkflowState
        if s not in {WorkflowState.CLOSED, WorkflowState.REJECTED, WorkflowState.ROLLED_BACK}
    ]
    total_tickets = db.query(func.count(Ticket.id)).scalar() or 0
    open_tickets = db.query(func.count(Ticket.id)).filter(Ticket.status.in_(open_states)).scalar() or 0
    processing = (
        db.query(func.count(Ticket.id))
        .filter(
            Ticket.status.in_(
                [
                    WorkflowState.INTERPRETING,
                    WorkflowState.RULE_RESOLVING,
                    WorkflowState.VALIDATING,
                    WorkflowState.TESTING,
                    WorkflowState.SANDBOXING,
                ]
            )
        )
        .scalar()
        or 0
    )
    awaiting = (
        db.query(func.count(Ticket.id)).filter(Ticket.status == WorkflowState.AWAITING_APPROVAL).scalar() or 0
    )
    high_risk = (
        db.query(func.count(Ticket.id)).filter(Ticket.risk_level.in_(["HIGH", "CRITICAL"])).scalar() or 0
    )
    closed = db.query(Ticket).filter(Ticket.closed_at.isnot(None)).all()
    durations = []
    for t in closed:
        if t.created_at and t.closed_at:
            durations.append((t.closed_at - t.created_at).total_seconds() / 3600)
    avg_res = sum(durations) / len(durations) if durations else 0
    median_res = 0
    if durations:
        s = sorted(durations)
        mid = len(s) // 2
        median_res = s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2

    prod_rules = (
        db.query(func.count(RuleDefinition.id)).filter(RuleDefinition.status == "ACTIVE").scalar() or 0
    )
    today = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    deployments_today = (
        db.query(func.count(Deployment.id)).filter(Deployment.created_at >= today).scalar() or 0
    )
    runs = db.query(TestRun).all()
    pass_rate = (
        (sum(1 for r in runs if r.regression_safety == "PASS") / len(runs)) if runs else 0
    )

    stages = (
        db.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
    )
    risks = (
        db.query(Ticket.risk_level, func.count(Ticket.id))
        .filter(Ticket.risk_level.isnot(None))
        .group_by(Ticket.risk_level)
        .all()
    )
    by_market = (
        db.query(Ticket.market_hint, func.count(Ticket.id))
        .filter(Ticket.market_hint.isnot(None))
        .group_by(Ticket.market_hint)
        .all()
    )
    by_change = (
        db.query(Ticket.change_type, func.count(Ticket.id))
        .filter(Ticket.change_type.isnot(None))
        .group_by(Ticket.change_type)
        .all()
    )
    recent_deps = (
        db.query(Deployment).order_by(Deployment.created_at.desc()).limit(8).all()
    )
    pending = (
        db.query(Ticket)
        .filter(Ticket.status == WorkflowState.AWAITING_APPROVAL)
        .order_by(Ticket.created_at.desc())
        .limit(8)
        .all()
    )
    rollbacks = db.query(func.count(RollbackEvent.id)).scalar() or 0
    all_deps = db.query(func.count(Deployment.id)).scalar() or 0
    fail_runs = sum(1 for r in runs if r.regression_safety != "PASS")

    return {
        "open_tickets": open_tickets,
        "processing": processing,
        "awaiting_approval": awaiting,
        "high_risk": high_risk,
        "average_resolution_hours": round(avg_res, 2),
        "median_resolution_hours": round(median_res, 2),
        "rules_in_production": prod_rules,
        "deployments_today": deployments_today,
        "regression_pass_rate": round(pass_rate, 4),
        "total_tickets": total_tickets,
        "rollback_rate": round((rollbacks / all_deps), 4) if all_deps else 0,
        "regression_failure_rate": round((fail_runs / len(runs)), 4) if runs else 0,
        "stage_distribution": [{"status": s, "count": c} for s, c in stages],
        "risk_distribution": [{"risk": r or "UNSCORED", "count": c} for r, c in risks],
        "tickets_by_market": [{"market": m or "n/a", "count": c} for m, c in by_market],
        "tickets_by_change_type": [{"change_type": t or "n/a", "count": c} for t, c in by_change],
        "recent_deployments": [
            {
                "id": d.id,
                "ticket_id": d.ticket_id,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in recent_deps
        ],
        "pending_approvals": [
            {
                "id": t.id,
                "ticket_number": t.ticket_number,
                "title": t.title,
                "risk_level": t.risk_level,
            }
            for t in pending
        ],
        "dataset_label": "Synthetic Demo Data",
    }
