from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.rules.dsl import ChangeIntent


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _eq(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return False
    return _norm(a) == _norm(b)


@dataclass
class MatrixCandidate:
    config_id: str
    rule_id: str
    market: str
    brand: str
    therapeutic_area: str
    string_type: str
    language: str
    old_value: str
    new_value: str | None
    static_link: str
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class MatrixResolution:
    selected: MatrixCandidate | None
    candidates: list[MatrixCandidate]
    status: str
    explanation: str


class ConfigurationMatrixResolver:
    """Score configuration-matrix rows on email resolution keys."""

    def resolve(self, intent: ChangeIntent, rows: list[dict[str, Any]]) -> MatrixResolution:
        string_type = (intent.string_type.value if intent.string_type else None) or intent.rule_category.value
        scored: list[MatrixCandidate] = []
        for row in rows:
            if (row.get("status") or "ACTIVE") != "ACTIVE":
                continue
            score = 0.0
            reasons: list[str] = []
            if _eq(row.get("market"), intent.market.value):
                score += 40
                reasons.append("market")
            if _eq(row.get("brand"), intent.brand.value):
                score += 30
                reasons.append("brand")
            if _eq(row.get("therapeutic_area"), intent.therapeutic_area.value):
                score += 15
                reasons.append("therapeutic_area")
            if _eq(row.get("string_type"), string_type):
                score += 20
                reasons.append("string_type")
            if _eq(row.get("language"), intent.language.value):
                score += 8
                reasons.append("language")
            hay = f"{row.get('old_value') or ''} {row.get('new_value') or ''}".lower()
            for token in (intent.old_value, intent.citation_to_remove, intent.remove_reference):
                if token and _norm(token) in hay:
                    score += 18
                    reasons.append(f"old_value:{token}")
                    break
            if score <= 0:
                continue
            scored.append(
                MatrixCandidate(
                    config_id=row["config_id"],
                    rule_id=row["rule_id"],
                    market=row.get("market") or "",
                    brand=row.get("brand") or "",
                    therapeutic_area=row.get("therapeutic_area") or "",
                    string_type=row.get("string_type") or "",
                    language=row.get("language") or "",
                    old_value=row.get("old_value") or "",
                    new_value=row.get("new_value"),
                    static_link=row.get("static_link") or "",
                    score=score,
                    reasons=reasons,
                )
            )
        scored.sort(key=lambda c: c.score, reverse=True)
        if not scored:
            return MatrixResolution(None, [], "MATRIX_MISS", "No configuration matrix row matched the intent keys.")
        top = scored[0]
        tied = [c for c in scored if c.score == top.score]
        if top.score < 70:
            return MatrixResolution(
                None,
                scored[:8],
                "MATRIX_MISS",
                f"Best matrix score {top.score} below threshold; falling back to 5-tier resolver.",
            )
        if len(tied) > 1:
            return MatrixResolution(
                None,
                scored[:8],
                "MATRIX_AMBIGUOUS",
                f"{len(tied)} matrix rows share score {top.score}.",
            )
        return MatrixResolution(
            top,
            scored[:8],
            "MATRIX_MATCHED",
            f"Matched {top.config_id} → {top.rule_id} ({', '.join(top.reasons)}).",
        )


def row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "config_id": row.config_id,
        "market": row.market,
        "country": row.country,
        "language": row.language,
        "brand": row.brand,
        "therapeutic_area": row.therapeutic_area,
        "string_type": row.string_type,
        "old_value": row.old_value,
        "new_value": row.new_value,
        "static_link": row.static_link,
        "rule_switch": row.rule_switch,
        "additional_params": row.additional_params,
        "rule_id": row.rule_id,
        "status": row.status,
        "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
    }
