import json

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import DbDep, UserDep
from app.core.errors import RuleOpsError
from app.models.audit import AuditEvent
from app.models.rule import RuleDefinition, RuleDependency, RuleInheritance, RuleScope, RuleVersion
from app.rules.dsl import ChangeIntent
from app.rules.resolver import RuleResolver

router = APIRouter(prefix="/rules", tags=["rules"])


class ResolveRequest(BaseModel):
    market: str | None = None
    brand: str | None = None
    therapeutic_area: str | None = None
    material_type: str | None = None
    rule_category: str | None = "DISCLAIMER"
    change_type: str = "TEXT_STRING_UPDATE"
    intent: str = "RESOLVE"


class ExecuteRequest(BaseModel):
    rule_id: str | None = None
    version_id: str | None = None
    market: str = ""
    brand: str = ""
    therapeutic_area: str = ""
    language: str = "EN"
    material_type: str = ""
    content: str = ""
    country: str = ""


@router.get("")
def list_rules(
    db: DbDep,
    user: UserDep,
    market: str | None = None,
    brand: str | None = None,
    scope_type: str | None = None,
    q: str | None = None,
    offset: int = 0,
    limit: int = 100,
) -> list[dict]:
    query = db.query(RuleDefinition)
    if q:
        query = query.filter(RuleDefinition.rule_id.ilike(f"%{q}%") | RuleDefinition.name.ilike(f"%{q}%"))
    rules = query.order_by(RuleDefinition.rule_id.asc()).offset(offset).limit(limit).all()
    return [_summary(db, r) for r in rules]


@router.post("/execute")
def execute_rules(payload: ExecuteRequest, db: DbDep, user: UserDep) -> dict:
    from app.rules.engine import ReviewContext, RuleExecutionEngine

    ctx = ReviewContext(
        market=payload.market,
        brand=payload.brand,
        therapeutic_area=payload.therapeutic_area,
        language=payload.language,
        material_type=payload.material_type,
        content=payload.content,
        country=payload.country,
    )
    bodies: list[dict] = []
    source = "production_catalog"
    if payload.version_id:
        ver = db.get(RuleVersion, payload.version_id)
        if ver is None:
            raise RuleOpsError("VERSION_NOT_FOUND", "Rule version not found", {"id": payload.version_id}, False, 404)
        bodies = [json.loads(ver.body_json)]
        source = f"version:{ver.id}"
    elif payload.rule_id:
        rule = _get(db, payload.rule_id)
        if not rule.production_version_id:
            raise RuleOpsError("NO_PRODUCTION_VERSION", "Rule has no production version", {"id": rule.rule_id}, False, 409)
        ver = db.get(RuleVersion, rule.production_version_id)
        if ver is None:
            raise RuleOpsError("VERSION_NOT_FOUND", "Production version missing", {"id": rule.rule_id}, False, 404)
        bodies = [json.loads(ver.body_json)]
        source = f"production:{rule.rule_id}:{ver.version_label}"
    else:
        rules = db.query(RuleDefinition).filter(RuleDefinition.status == "ACTIVE").all()
        for rule in rules:
            if not rule.production_version_id:
                continue
            ver = db.get(RuleVersion, rule.production_version_id)
            if ver:
                bodies.append(json.loads(ver.body_json))
    result = RuleExecutionEngine().execute_many(bodies, ctx)
    out = result.as_dict()
    out["rules_evaluated"] = len(bodies)
    out["source"] = source
    return out


@router.get("/{rule_id}")
def get_rule(rule_id: str, db: DbDep, user: UserDep) -> dict:
    rule = _get(db, rule_id)
    scopes = db.query(RuleScope).filter(RuleScope.rule_id == rule.id).all()
    versions = db.query(RuleVersion).filter(RuleVersion.rule_id == rule.id).order_by(RuleVersion.version_number).all()
    deps = db.query(RuleDependency).filter(RuleDependency.rule_id == rule.id).all()
    inh = db.query(RuleInheritance).filter(RuleInheritance.child_rule_id == rule.id).all()
    prod = next((v for v in versions if v.id == rule.production_version_id), None)
    history = (
        db.query(AuditEvent)
        .filter(AuditEvent.entity_id.in_([rule.id, *[v.id for v in versions]]))
        .order_by(AuditEvent.timestamp.desc())
        .limit(40)
        .all()
    )
    return {
        "id": rule.id,
        "rule_id": rule.rule_id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "rule_category": rule.rule_category,
        "status": rule.status,
        "priority": rule.priority,
        "description": rule.description,
        "production_version_id": rule.production_version_id,
        "lock_version": rule.lock_version,
        "scopes": [
            {
                "scope_type": s.scope_type,
                "market": s.market,
                "brand": s.brand,
                "therapeutic_area": s.therapeutic_area,
                "material_type": s.material_type,
                "language": s.language,
                "country": s.country,
            }
            for s in scopes
        ],
        "current_body": json.loads(prod.body_json) if prod else None,
        "current_checksum": prod.checksum_sha256 if prod else None,
        "versions": [
            {
                "id": v.id,
                "version_label": v.version_label,
                "version_number": v.version_number,
                "is_production": v.is_production,
                "checksum_sha256": v.checksum_sha256,
                "change_summary": v.change_summary,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ],
        "dependencies": [{"depends_on_rule_id": d.depends_on_rule_id, "type": d.dependency_type, "notes": d.notes} for d in deps],
        "inherited": [{"parent_rule_id": i.parent_rule_id, "type": i.inheritance_type} for i in inh],
        "history": [{"event_type": h.event_type, "timestamp": h.timestamp.isoformat(), "checksum": h.checksum} for h in history],
    }


@router.get("/{rule_id}/versions")
def versions(rule_id: str, db: DbDep, user: UserDep) -> list[dict]:
    rule = _get(db, rule_id)
    rows = db.query(RuleVersion).filter(RuleVersion.rule_id == rule.id).order_by(RuleVersion.version_number).all()
    return [
        {
            "id": v.id,
            "version_label": v.version_label,
            "is_production": v.is_production,
            "checksum_sha256": v.checksum_sha256,
            "body": json.loads(v.body_json),
            "change_summary": v.change_summary,
        }
        for v in rows
    ]


@router.get("/{rule_id}/dependencies")
def dependencies(rule_id: str, db: DbDep, user: UserDep) -> list[dict]:
    rule = _get(db, rule_id)
    rows = db.query(RuleDependency).filter(RuleDependency.rule_id == rule.id).all()
    return [{"depends_on_rule_id": d.depends_on_rule_id, "type": d.dependency_type, "notes": d.notes} for d in rows]


@router.post("/resolve")
def resolve(payload: ResolveRequest, db: DbDep, user: UserDep) -> dict:
    from app.api.tickets import serialize_ticket_workspace  # noqa: F401
    from app.workflow.orchestrator import TicketOrchestrator

    orch = TicketOrchestrator(db)
    rules = orch._load_rule_dicts()
    intent = ChangeIntent(
        change_type=payload.change_type,
        intent=payload.intent,
        market={"value": payload.market, "confidence": 0.9},
        brand={"value": payload.brand, "confidence": 0.9},
        therapeutic_area={"value": payload.therapeutic_area, "confidence": 0.9},
        material_type={"value": payload.material_type, "confidence": 0.7},
        rule_category={"value": payload.rule_category, "confidence": 0.8},
    )
    result = RuleResolver().resolve(intent, rules)
    return {
        "selected": result.selected.__dict__ if result.selected else None,
        "candidates": [c.__dict__ for c in result.candidates],
        "hierarchy_path": result.hierarchy_path,
        "explanation": result.explanation,
        "confidence": result.confidence,
        "overridden_rule_ids": result.overridden_rule_ids,
    }


def _get(db: Session, rule_id: str) -> RuleDefinition:
    rule = (
        db.query(RuleDefinition)
        .filter((RuleDefinition.id == rule_id) | (RuleDefinition.rule_id == rule_id))
        .one_or_none()
    )
    if rule is None:
        raise RuleOpsError("RULE_NOT_FOUND", "Rule not found", {"id": rule_id}, False, 404)
    return rule


def _summary(db: Session, rule: RuleDefinition) -> dict:
    scope = db.query(RuleScope).filter(RuleScope.rule_id == rule.id).first()
    return {
        "id": rule.id,
        "rule_id": rule.rule_id,
        "name": rule.name,
        "rule_type": rule.rule_type,
        "rule_category": rule.rule_category,
        "status": rule.status,
        "scope_type": scope.scope_type if scope else None,
        "market": scope.market if scope else None,
        "brand": scope.brand if scope else None,
        "therapeutic_area": scope.therapeutic_area if scope else None,
        "material_type": scope.material_type if scope else None,
        "production_version_id": rule.production_version_id,
    }
