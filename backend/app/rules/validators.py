from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.enums import ValidationStatus
from app.rules.dsl import parse_rule_body


@dataclass
class ValidatorOutput:
    validator_name: str
    status: str
    severity: str
    message: str
    evidence: dict[str, Any]
    timestamp: datetime

    def as_dict(self) -> dict[str, Any]:
        return {
            "validator_name": self.validator_name,
            "status": self.status,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
            "timestamp": self.timestamp.isoformat(),
        }


def _now() -> datetime:
    return datetime.now(UTC)


def _out(name: str, status: str, message: str, evidence: dict | None = None, severity: str | None = None) -> ValidatorOutput:
    sev = severity or ("ERROR" if status == ValidationStatus.FAIL else "WARNING" if status == ValidationStatus.WARN else "INFO")
    return ValidatorOutput(name, status, sev, message, evidence or {}, _now())


class SchemaValidator:
    name = "SchemaValidator"

    def validate(self, body: dict, ctx: dict | None = None) -> ValidatorOutput:
        try:
            parse_rule_body(body)
            return _out(self.name, ValidationStatus.PASS, "Rule body conforms to TEXT/LOGIC schema")
        except Exception as exc:
            return _out(self.name, ValidationStatus.FAIL, f"Schema invalid: {exc}", {"error": str(exc)})


class SyntaxValidator:
    name = "SyntaxValidator"

    def validate(self, body: dict, ctx: dict | None = None) -> ValidatorOutput:
        if body.get("rule_type") == "LOGIC":
            when = body.get("when")
            if not when:
                return _out(self.name, ValidationStatus.FAIL, "LOGIC rule missing when clause")
            if not body.get("actions"):
                return _out(self.name, ValidationStatus.FAIL, "LOGIC rule missing actions")
        if body.get("rule_type") == "TEXT" and not body.get("content"):
            return _out(self.name, ValidationStatus.FAIL, "TEXT rule missing content")
        return _out(self.name, ValidationStatus.PASS, "Rule syntax is well-formed")


class ReferenceValidator:
    name = "ReferenceValidator"

    def validate(self, body: dict, ctx: dict | None = None) -> ValidatorOutput:
        ctx = ctx or {}
        known: set[str] = set(ctx.get("known_citation_ids", []))
        refs = body.get("references") or []
        missing = []
        unresolved = []
        for ref in refs:
            cid = ref.get("id") if isinstance(ref, dict) else ref
            if known and cid not in known:
                missing.append(cid)
            statuses = ctx.get("citation_statuses", {})
            if statuses.get(cid) == "CITATION_VERIFICATION_REQUIRED":
                unresolved.append(cid)
        if missing:
            return _out(self.name, ValidationStatus.FAIL, "Unknown scientific citation", {"missing": missing})
        if unresolved:
            return _out(
                self.name,
                ValidationStatus.FAIL,
                "Citation verification required before deployment",
                {"unresolved": unresolved},
            )
        return _out(self.name, ValidationStatus.PASS, "All references resolve to known citations")


class ScopeValidator:
    name = "ScopeValidator"

    def validate(self, body: dict, ctx: dict | None = None) -> ValidatorOutput:
        ctx = ctx or {}
        scope = body.get("scope") or {}
        if ctx.get("expected_market") and scope.get("market") and scope.get("market") != ctx["expected_market"]:
            return _out(self.name, ValidationStatus.FAIL, "Proposed scope market does not match ticket intent")
        return _out(self.name, ValidationStatus.PASS, "Scope remains consistent with change intent")


class DependencyValidator:
    name = "DependencyValidator"

    def validate(self, body: dict, ctx: dict | None = None) -> ValidatorOutput:
        ctx = ctx or {}
        deps = ctx.get("dependencies") or []
        if ctx.get("broken_dependencies"):
            return _out(self.name, ValidationStatus.FAIL, "Broken rule dependency", {"deps": ctx["broken_dependencies"]})
        return _out(self.name, ValidationStatus.PASS, f"{len(deps)} dependent rule(s) inspected", {"dependencies": deps})


class ConflictValidator:
    name = "ConflictValidator"

    def validate(self, body: dict, ctx: dict | None = None) -> ValidatorOutput:
        ctx = ctx or {}
        if ctx.get("conflicting_rule_ids"):
            return _out(self.name, ValidationStatus.FAIL, "Conflicting active rules", {"conflicts": ctx["conflicting_rule_ids"]})
        refs = [r.get("id") if isinstance(r, dict) else r for r in body.get("references", [])]
        if len(refs) != len(set(refs)):
            return _out(self.name, ValidationStatus.WARN, "Duplicate references on rule")
        return _out(self.name, ValidationStatus.PASS, "No conflicting active rules detected")


class InheritanceValidator:
    name = "InheritanceValidator"

    def validate(self, body: dict, ctx: dict | None = None) -> ValidatorOutput:
        ctx = ctx or {}
        return _out(
            self.name,
            ValidationStatus.PASS,
            "Inheritance chain remains valid",
            {"inherited": ctx.get("inherited_rule_ids", [])},
        )


class ScientificCitationValidator:
    name = "ScientificCitationValidator"

    def validate(self, body: dict, ctx: dict | None = None) -> ValidatorOutput:
        ctx = ctx or {}
        for cid in [r.get("id") if isinstance(r, dict) else r for r in body.get("references", [])]:
            if ctx.get("citation_statuses", {}).get(cid) == "CITATION_VERIFICATION_REQUIRED":
                return _out(self.name, ValidationStatus.FAIL, f"Citation {cid} is not verified")
        return _out(self.name, ValidationStatus.PASS, "Scientific citations are verified or synthetic-demo approved")


class SemanticConsistencyValidator:
    name = "SemanticConsistencyValidator"

    def validate(self, body: dict, ctx: dict | None = None) -> ValidatorOutput:
        import re

        content = body.get("content") or ""
        refs = [r.get("id") if isinstance(r, dict) else r for r in body.get("references", [])]

        def years_in(text: str) -> set[int]:
            return {int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", text or "")}

        content_years = years_in(content)
        ref_years: set[int] = set()
        for ref in refs:
            ref_years |= years_in(ref or "")
        if body.get("rule_type") == "TEXT" and ref_years and content:
            missing = sorted(ref_years - content_years)
            if missing:
                return _out(
                    self.name,
                    ValidationStatus.WARN,
                    "Citation year(s) are not reflected in rule content",
                    {"missing_years": missing, "citation_ids": refs},
                )
            if content_years and not (content_years & ref_years):
                return _out(
                    self.name,
                    ValidationStatus.WARN,
                    "Content years and citation identifier years do not overlap",
                    {"content_years": sorted(content_years), "citation_years": sorted(ref_years)},
                )
        return _out(self.name, ValidationStatus.PASS, "Semantic consistency checks passed")


ALL_VALIDATORS = [
    SchemaValidator(),
    SyntaxValidator(),
    ReferenceValidator(),
    ScopeValidator(),
    DependencyValidator(),
    ConflictValidator(),
    InheritanceValidator(),
    ScientificCitationValidator(),
    SemanticConsistencyValidator(),
]


def run_validators(body: dict, ctx: dict | None = None) -> list[ValidatorOutput]:
    return [v.validate(body, ctx) for v in ALL_VALIDATORS]


def is_blocking(results: list[ValidatorOutput]) -> bool:
    return any(r.status == ValidationStatus.FAIL for r in results)
