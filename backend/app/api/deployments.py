from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import DbDep, UserDep
from app.core.enums import RoleName
from app.core.errors import ForbiddenAction, RuleOpsError
from app.models.deployment import Deployment, RollbackEvent
from app.models.rule import RuleDefinition
from app.services.governance import rollback_rule

router = APIRouter(tags=["deployments"])


class RollbackIn(BaseModel):
    target_version_id: str
    reason: str
    ticket_id: str | None = None
    rule_id: str | None = None


@router.get("/deployments")
def list_deployments(db: DbDep, user: UserDep, offset: int = 0, limit: int = 50) -> list[dict]:
    rows = db.query(Deployment).order_by(Deployment.created_at.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": d.id,
            "ticket_id": d.ticket_id,
            "rule_id": d.rule_id,
            "from_version_id": d.from_version_id,
            "to_version_id": d.to_version_id,
            "status": d.status,
            "smoke_test_status": d.smoke_test_status,
            "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None,
        }
        for d in rows
    ]


@router.post("/deployments/{deployment_id}/rollback")
def rollback(deployment_id: str, payload: RollbackIn, db: DbDep, user: UserDep) -> dict:
    if not set(user.role_names()).intersection({RoleName.ADMIN.value, RoleName.MLR_ADMIN.value}):
        raise ForbiddenAction("Rollback requires MLR_ADMIN or ADMIN")
    dep = db.get(Deployment, deployment_id)
    if dep is None:
        raise RuleOpsError("DEPLOYMENT_NOT_FOUND", "Deployment not found", status_code=404)
    event = rollback_rule(
        db,
        payload.rule_id or dep.rule_id,
        payload.target_version_id,
        payload.reason,
        user,
        payload.ticket_id or dep.ticket_id,
    )
    rule = db.get(RuleDefinition, event.rule_id)
    return {
        "rollback_id": event.id,
        "production_version_id": rule.production_version_id if rule else None,
        "smoke_test_status": event.smoke_test_status,
    }


@router.get("/rollbacks")
def list_rollbacks(db: DbDep, user: UserDep) -> list[dict]:
    rows = db.query(RollbackEvent).order_by(RollbackEvent.created_at.desc()).limit(50).all()
    return [
        {
            "id": r.id,
            "rule_id": r.rule_id,
            "from_version_id": r.from_version_id,
            "to_version_id": r.to_version_id,
            "reason": r.reason,
            "smoke_test_status": r.smoke_test_status,
        }
        for r in rows
    ]
