from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import DbDep, UserDep
from app.core.errors import RuleOpsError
from app.models.configuration import ConfigurationMatrixRow
from app.rules.dsl import ChangeIntent, ChangeIntentField
from app.rules.matrix import ConfigurationMatrixResolver, row_to_dict

router = APIRouter(tags=["configurations"])

CSV_FIELDS = [
    "config_id",
    "market",
    "country",
    "language",
    "brand",
    "therapeutic_area",
    "string_type",
    "old_value",
    "new_value",
    "static_link",
    "rule_switch",
    "additional_params",
    "rule_id",
    "status",
]


class ResolveIn(BaseModel):
    market: str | None = None
    brand: str | None = None
    therapeutic_area: str | None = None
    string_type: str | None = None
    language: str | None = None
    old_value: str | None = None
    citation_to_remove: str | None = None


def _field(value: str | None) -> ChangeIntentField:
    return ChangeIntentField(value=value, confidence=0.9 if value else 0.0)


@router.get("/configurations")
def list_configurations(
    db: DbDep,
    user: UserDep,
    market: str | None = None,
    language: str | None = None,
    string_type: str | None = None,
    brand: str | None = None,
) -> dict:
    q = db.query(ConfigurationMatrixRow)
    if market:
        q = q.filter(ConfigurationMatrixRow.market == market)
    if language:
        q = q.filter(ConfigurationMatrixRow.language == language)
    if string_type:
        q = q.filter(ConfigurationMatrixRow.string_type == string_type)
    if brand:
        q = q.filter(ConfigurationMatrixRow.brand == brand)
    rows = q.order_by(ConfigurationMatrixRow.config_id.asc()).all()
    languages = {r.language for r in db.query(ConfigurationMatrixRow.language).all()}
    return {
        "count": len(rows),
        "language_count": len(languages),
        "rows": [row_to_dict(r) for r in rows],
    }


@router.get("/configurations/export.csv")
def export_csv(db: DbDep, user: UserDep, changed_since: str | None = Query(default=None)):
    q = db.query(ConfigurationMatrixRow)
    if changed_since:
        try:
            since = datetime.fromisoformat(changed_since.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuleOpsError("INVALID_SINCE", "changed_since must be ISO-8601", retryable=False, status_code=400) from exc
        q = q.filter(ConfigurationMatrixRow.updated_at >= since)
    rows = q.order_by(ConfigurationMatrixRow.config_id.asc()).all()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: getattr(row, k) or "" for k in CSV_FIELDS})
    data = buf.getvalue()
    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=configuration_matrix.csv"},
    )


@router.post("/configurations/import")
async def import_csv(db: DbDep, user: UserDep, file: UploadFile = File(...)) -> dict:
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        return {"imported": 0, "updated": 0, "control_count": "0 records"}
    imported = 0
    updated = 0
    for rec in reader:
        config_id = (rec.get("config_id") or "").strip()
        if not config_id:
            continue
        existing = db.query(ConfigurationMatrixRow).filter(ConfigurationMatrixRow.config_id == config_id).one_or_none()
        values = {k: (rec.get(k) or "").strip() or None for k in CSV_FIELDS if k != "config_id"}
        values["config_id"] = config_id
        values["market"] = values.get("market") or ""
        values["country"] = values.get("country") or ""
        values["language"] = values.get("language") or "EN"
        values["brand"] = values.get("brand") or ""
        values["therapeutic_area"] = values.get("therapeutic_area") or ""
        values["string_type"] = values.get("string_type") or "DISCLAIMER"
        values["old_value"] = values.get("old_value") or ""
        values["static_link"] = values.get("static_link") or ""
        values["rule_switch"] = values.get("rule_switch") or "ON"
        values["additional_params"] = values.get("additional_params") or "{}"
        values["rule_id"] = values.get("rule_id") or ""
        values["status"] = values.get("status") or "ACTIVE"
        if existing:
            for key, val in values.items():
                setattr(existing, key, val)
            updated += 1
        else:
            db.add(ConfigurationMatrixRow(**values))
            imported += 1
    db.flush()
    total = imported + updated
    return {
        "imported": imported,
        "updated": updated,
        "control_count": f"{total} records" if total else "0 records",
    }


@router.post("/configurations/resolve")
def resolve_configuration(payload: ResolveIn, db: DbDep, user: UserDep) -> dict:
    intent = ChangeIntent(
        change_type="TEXT_STRING_UPDATE",
        intent="MATRIX_RESOLVE",
        market=_field(payload.market),
        brand=_field(payload.brand),
        therapeutic_area=_field(payload.therapeutic_area),
        string_type=_field(payload.string_type),
        rule_category=_field(payload.string_type),
        language=_field(payload.language),
        old_value=payload.old_value,
        citation_to_remove=payload.citation_to_remove,
    )
    rows = [row_to_dict(r) for r in db.query(ConfigurationMatrixRow).all()]
    result = ConfigurationMatrixResolver().resolve(intent, rows)
    return {
        "status": result.status,
        "explanation": result.explanation,
        "selected": result.selected.__dict__ if result.selected else None,
        "candidates": [c.__dict__ for c in result.candidates],
    }


@router.get("/configurations/{config_id}")
def get_configuration(config_id: str, db: DbDep, user: UserDep) -> dict:
    row = db.query(ConfigurationMatrixRow).filter(ConfigurationMatrixRow.config_id == config_id).one_or_none()
    if row is None:
        raise RuleOpsError("CONFIG_NOT_FOUND", "Configuration not found", {"config_id": config_id}, False, 404)
    return row_to_dict(row)
