from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.errors import StaleBaseVersion
from app.rules.checksum import rule_checksum
from app.rules.dsl import parse_rule_body
from app.rules.engine import ReviewContext, RuleExecutionEngine


@dataclass
class SmokeResult:
    status: str
    notes: str


class DeploymentEngine:
    def assert_not_stale(self, production_version_id: str, base_version_id: str) -> None:
        if production_version_id != base_version_id:
            raise StaleBaseVersion(
                "Production version has moved since this proposal was created",
                {"production_version_id": production_version_id, "base_version_id": base_version_id},
            )

    def smoke_test(self, proposed_body: dict[str, Any]) -> SmokeResult:
        parse_rule_body(proposed_body)
        engine = RuleExecutionEngine()
        ctx = ReviewContext(
            market=(proposed_body.get("scope") or {}).get("market", "US"),
            brand=(proposed_body.get("scope") or {}).get("brand", "Drug A"),
            therapeutic_area=(proposed_body.get("scope") or {}).get("therapeutic_area", "Cardiovascular"),
            material_type="Promotional",
            content="Drug A cardiovascular promotional disclaimer 2026 clinical trial",
        )
        result = engine.execute_rule(proposed_body, ctx)
        checksum = rule_checksum(proposed_body)
        return SmokeResult(
            status="PASS",
            notes=f"Smoke executed. checksum={checksum[:12]} flags={len(result.flags)}",
        )
