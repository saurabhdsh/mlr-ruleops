from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session, selectinload

from app.ai.factory import get_llm_provider
from app.approvals.policy import ApprovalPolicyEngine
from app.audit.ledger import AuditLedger
from app.core.config import settings
from app.core.enums import ActorType, WorkflowState
from app.core.errors import LowAIConfidence, RuleNotFound, ValidationFailed
from app.models.approval import ApprovalRequest
from app.models.citation import ScientificCitation
from app.models.configuration import ConfigurationMatrixRow
from app.models.rule import (
    ChangeOperation,
    ChangeProposal,
    ChangeRequest,
    RuleDefinition,
    RuleDependency,
    RuleInheritance,
    RuleScope,
    RuleVersion,
)
from app.models.ticket import ExtractedEntity, Ticket, TicketAnalysis
from app.models.validation import (
    HistoricalReview,
    ImpactAnalysis,
    RiskAssessment,
    TestResult,
    TestRun,
    ValidationResult,
    ValidationRun,
)
from app.risk.engine import RiskEngine
from app.rules.checksum import rule_checksum
from app.rules.mutation import RuleMutationEngine
from app.rules.matrix import ConfigurationMatrixResolver, row_to_dict
from app.rules.resolver import RuleCandidate, RuleResolver
from app.rules.validators import is_blocking, run_validators
from app.testing_engine.impact import ImpactAnalyzer
from app.testing_engine.regression import RegressionEngine
from app.testing_engine.sandbox import SandboxSession
from app.workflow.events import publish_ticket_event
from app.workflow.transitions import transition


class TicketOrchestrator:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit = AuditLedger(db)
        self.seq = 0

    def emit(self, ticket: Ticket, event_type: str, message: str, payload: dict | None = None) -> None:
        self.seq += 1
        ev = self.audit.workflow(ticket.id, event_type, message, payload, self.seq)
        self.db.commit()
        publish_ticket_event(
            ticket.id,
            {
                "event_type": event_type,
                "message": message,
                "status": ticket.status,
                "sequence": self.seq,
                "timestamp": ev.timestamp.isoformat(),
                "payload": payload or {},
            },
        )

    def process(self, ticket_id: str, actor_id: str = "system") -> Ticket:
        ticket = self.db.get(Ticket, ticket_id)
        if ticket is None:
            raise RuleNotFound("Ticket not found", {"ticket_id": ticket_id})
        reprocessable = {
            WorkflowState.RECEIVED,
            WorkflowState.NORMALIZED,
            WorkflowState.NEEDS_CLARIFICATION,
            WorkflowState.VALIDATION_FAILED,
            WorkflowState.REGRESSION_FAILED,
            WorkflowState.PROPOSAL_READY,
            WorkflowState.AWAITING_APPROVAL,
            WorkflowState.APPROVED,
            WorkflowState.REJECTED,
            WorkflowState.DEPLOYED,
            WorkflowState.ROLLED_BACK,
            WorkflowState.CLOSED,
        }
        current = WorkflowState(ticket.status)
        if current in reprocessable and current != WorkflowState.RECEIVED:
            ticket.status = WorkflowState.RECEIVED.value
        if ticket.processing_lock and current not in reprocessable:
            return ticket
        ticket.processing_lock = 1
        self.seq = 0
        self.db.flush()

        self.audit.record(
            event_type="TICKET_PROCESS_STARTED",
            entity_type="ticket",
            entity_id=ticket.id,
            actor_type=ActorType.WORKER,
            actor_id=actor_id,
            ticket_id=ticket.id,
            new_state={"status": ticket.status},
        )
        self.emit(ticket, "TICKET_RECEIVED", "Ticket received")

        if ticket.status == WorkflowState.RECEIVED:
            transition(ticket, WorkflowState.NORMALIZED)
            self.emit(ticket, "TICKET_NORMALIZED", "Ticket normalized")
            self.audit.record(
                event_type="TICKET_NORMALIZED",
                entity_type="ticket",
                entity_id=ticket.id,
                ticket_id=ticket.id,
                new_state={"status": ticket.status},
            )

        transition(ticket, WorkflowState.INTERPRETING)
        self.emit(ticket, "AI_INTERPRETATION_STARTED", "Interpreting request")
        self.audit.record(
            event_type="AI_INTERPRETATION_STARTED",
            entity_type="ticket",
            entity_id=ticket.id,
            actor_type=ActorType.AI,
            ticket_id=ticket.id,
        )

        provider = get_llm_provider()
        intent = provider.interpret_ticket(
            ticket.title,
            ticket.description,
            {
                "market": ticket.market_hint,
                "brand": ticket.brand_hint,
                "therapeutic_area": ticket.therapeutic_area_hint,
                "language": ticket.language_hint,
            },
        )
        from app.ai.grounding import ground_intent_citations

        intent = ground_intent_citations(
            intent,
            ticket.title,
            ticket.description,
            self.db.query(ScientificCitation).all(),
        )
        ticket.change_type = intent.change_type

        analysis = TicketAnalysis(
            ticket_id=ticket.id,
            provider_name=provider.name,
            model_name=provider.model,
            is_local_fallback=provider.is_local_fallback,
            prompt_template_version=settings.prompt_template_version,
            output_schema_version=settings.output_schema_version,
            structured_output=intent.model_dump_json(),
            decision_summary=intent.decision_summary,
            overall_confidence=intent.overall_confidence,
            sources_used=json.dumps(self._sources_for(ticket, intent)),
            completed_at=datetime.now(UTC),
        )
        self.db.add(analysis)
        self.db.flush()
        for field_name in (
            "market",
            "brand",
            "therapeutic_area",
            "language",
            "material_type",
            "rule_category",
            "string_type",
        ):
            field = getattr(intent, field_name)
            self.db.add(
                ExtractedEntity(
                    analysis_id=analysis.id,
                    field_name=field_name,
                    value=field.value or "",
                    confidence=field.confidence,
                )
            )
        self.emit(
            ticket,
            "AI_INTERPRETATION_COMPLETED",
            "Entities extracted",
            {
                "provider": provider.name,
                "is_local_fallback": provider.is_local_fallback,
                "confidence": intent.overall_confidence,
            },
        )
        self.audit.record(
            event_type="AI_INTERPRETATION_COMPLETED",
            entity_type="ticket_analysis",
            entity_id=analysis.id,
            actor_type=ActorType.AI,
            ticket_id=ticket.id,
            new_state=json.loads(intent.model_dump_json()),
        )

        if intent.overall_confidence < settings.llm_confidence_threshold or intent.ambiguities:
            transition(ticket, WorkflowState.NEEDS_CLARIFICATION)
            ticket.processing_lock = 0
            self.emit(ticket, "NEEDS_CLARIFICATION", "Confidence below threshold or missing fields")
            return ticket

        transition(ticket, WorkflowState.RULE_RESOLVING)
        self.emit(ticket, "RULE_SEARCH_STARTED", "Searching configuration matrix then rule hierarchy")

        matrix_rows = [row_to_dict(r) for r in self.db.query(ConfigurationMatrixRow).all()]
        matrix = ConfigurationMatrixResolver().resolve(intent, matrix_rows)
        self.emit(
            ticket,
            matrix.status,
            matrix.explanation,
            {
                "config_id": matrix.selected.config_id if matrix.selected else None,
                "rule_id": matrix.selected.rule_id if matrix.selected else None,
                "candidates": [
                    {"config_id": c.config_id, "rule_id": c.rule_id, "score": c.score}
                    for c in matrix.candidates
                ],
                "selected": {
                    "config_id": matrix.selected.config_id,
                    "rule_id": matrix.selected.rule_id,
                    "market": matrix.selected.market,
                    "brand": matrix.selected.brand,
                    "therapeutic_area": matrix.selected.therapeutic_area,
                    "string_type": matrix.selected.string_type,
                    "language": matrix.selected.language,
                    "old_value": matrix.selected.old_value,
                    "new_value": matrix.selected.new_value,
                    "static_link": matrix.selected.static_link,
                    "score": matrix.selected.score,
                    "reasons": matrix.selected.reasons,
                }
                if matrix.selected
                else None,
            },
        )

        rules = self._load_rule_dicts()
        inheritances = [
            {"child_rule_id": i.child_rule_id, "parent_rule_id": i.parent_rule_id}
            for i in self.db.query(RuleInheritance).all()
        ]
        deps = [
            {"rule_id": d.rule_id, "depends_on_rule_id": d.depends_on_rule_id}
            for d in self.db.query(RuleDependency).all()
        ]
        resolution = RuleResolver().resolve(intent, rules, inheritances, deps)
        if matrix.selected:
            pinned = self.db.query(RuleDefinition).filter(RuleDefinition.rule_id == matrix.selected.rule_id).one_or_none()
            if pinned:
                match = next((c for c in resolution.candidates if c.rule_id == pinned.rule_id), None)
                resolution.selected = match or RuleCandidate(
                    rule_pk=pinned.id,
                    rule_id=pinned.rule_id,
                    name=pinned.name,
                    scope_type="MARKET_BRAND",
                    market=matrix.selected.market,
                    brand=matrix.selected.brand,
                    therapeutic_area=matrix.selected.therapeutic_area,
                    material_type=None,
                    category=matrix.selected.string_type,
                    priority=pinned.priority,
                    match_score=matrix.selected.score,
                    reasons=["matrix:" + matrix.selected.config_id],
                )
                resolution.explanation = f"{matrix.explanation} {resolution.explanation}"
        if resolution.selected is None:
            transition(ticket, WorkflowState.NEEDS_CLARIFICATION)
            ticket.processing_lock = 0
            self.emit(ticket, "RULE_NOT_FOUND", "No matching rule for interpreted intent")
            return ticket

        self.emit(
            ticket,
            "CANDIDATES_FOUND",
            f"{len(resolution.candidates)} candidates found",
            {"count": len(resolution.candidates)},
        )
        transition(ticket, WorkflowState.RULE_RESOLVED)
        self.emit(
            ticket,
            "TARGET_RULE_SELECTED",
            f"Target rule selected: {resolution.selected.rule_id}",
            {"rule_id": resolution.selected.rule_id, "confidence": resolution.confidence},
        )
        self.audit.record(
            event_type="TARGET_RULE_SELECTED",
            entity_type="rule",
            entity_id=resolution.selected.rule_pk,
            ticket_id=ticket.id,
            new_state={"rule_id": resolution.selected.rule_id, "explanation": resolution.explanation},
        )

        rule = (
            self.db.query(RuleDefinition)
            .options(selectinload(RuleDefinition.versions), selectinload(RuleDefinition.scopes))
            .filter(RuleDefinition.id == resolution.selected.rule_pk)
            .one()
        )
        prod = next((v for v in rule.versions if v.id == rule.production_version_id), None)
        if prod is None:
            prod = max(rule.versions, key=lambda v: v.version_number)
        current_body = json.loads(prod.body_json)
        self.emit(ticket, "CURRENT_RULE_RETRIEVED", "Current rule retrieved")

        transition(ticket, WorkflowState.PROPOSING_CHANGE)
        proposal_payload = provider.propose_change(intent, current_body)
        proposal_payload["target_rule_id"] = rule.rule_id
        mutation = RuleMutationEngine().apply(current_body, proposal_payload["operations"])

        cr = ChangeRequest(
            ticket_id=ticket.id,
            change_type=intent.change_type,
            summary=proposal_payload.get("reason") or intent.decision_summary,
        )
        self.db.add(cr)
        self.db.flush()

        proposal = ChangeProposal(
            ticket_id=ticket.id,
            change_request_id=cr.id,
            target_rule_id=rule.id,
            base_rule_version_id=prod.id,
            proposed_body_json=json.dumps(mutation.proposed_body),
            proposed_checksum=mutation.checksum,
            reason=proposal_payload.get("reason") or "",
            status="READY",
            provider_name=provider.name,
            model_name=provider.model,
            prompt_template_version=settings.prompt_template_version,
            output_schema_version=settings.output_schema_version,
            decision_record=resolution.explanation,
            sources_used=analysis.sources_used,
            semantic_diff_json=json.dumps(mutation.diff),
        )
        self.db.add(proposal)
        self.db.flush()
        for i, op in enumerate(proposal_payload["operations"]):
            self.db.add(
                ChangeOperation(
                    proposal_id=proposal.id,
                    sequence=i,
                    operation=op.get("operation", ""),
                    path=op.get("path") or "",
                    value=json.dumps(op.get("value")),
                    old_value=json.dumps(op.get("old_value")) if op.get("old_value") is not None else None,
                )
            )
        ticket.current_proposal_id = proposal.id
        transition(ticket, WorkflowState.PROPOSAL_READY)
        self.emit(ticket, "PROPOSAL_CREATED", "Proposed update generated")
        self.audit.record(
            event_type="CHANGE_PROPOSAL_CREATED",
            entity_type="proposal",
            entity_id=proposal.id,
            ticket_id=ticket.id,
            checksum=mutation.checksum,
        )

        if not self._run_validation(ticket, proposal, mutation.proposed_body, intent, deps, inheritances, resolution):
            ticket.processing_lock = 0
            ticket.processed_at = datetime.now(UTC)
            self.db.flush()
            return ticket
        self._run_tests(ticket, proposal, rule, mutation.proposed_body, intent)
        ticket.processing_lock = 0
        ticket.processed_at = datetime.now(UTC)
        self.db.flush()
        return ticket

    def rerun_validation(self, proposal_id: str) -> None:
        proposal = self.db.get(ChangeProposal, proposal_id)
        if proposal is None:
            raise RuleNotFound("Proposal not found", {"proposal_id": proposal_id})
        ticket = self.db.get(Ticket, proposal.ticket_id)
        if ticket is None:
            raise RuleNotFound("Ticket not found", {"ticket_id": proposal.ticket_id})
        body = json.loads(proposal.proposed_body_json)
        from app.models.ticket import TicketAnalysis
        from app.rules.dsl import ChangeIntent

        analysis = (
            self.db.query(TicketAnalysis)
            .filter(TicketAnalysis.ticket_id == ticket.id)
            .order_by(TicketAnalysis.created_at.desc())
            .first()
        )
        intent = ChangeIntent.model_validate_json(analysis.structured_output) if analysis else ChangeIntent(
            change_type="TEXT_STRING_UPDATE", intent="RERUN"
        )
        deps = [{"rule_id": d.rule_id, "depends_on_rule_id": d.depends_on_rule_id} for d in self.db.query(RuleDependency).all()]
        class _Res:
            inherited_rule_ids = []
        self._run_validation(ticket, proposal, body, intent, deps, [], _Res(), skip_transition=True)

    def rerun_tests(self, proposal_id: str) -> None:
        proposal = self.db.get(ChangeProposal, proposal_id)
        if proposal is None:
            raise RuleNotFound("Proposal not found", {"proposal_id": proposal_id})
        ticket = self.db.get(Ticket, proposal.ticket_id)
        rule = self.db.get(RuleDefinition, proposal.target_rule_id)
        if ticket is None or rule is None:
            raise RuleNotFound("Ticket or target rule missing", {"proposal_id": proposal_id})
        body = json.loads(proposal.proposed_body_json)
        from app.models.ticket import TicketAnalysis
        from app.rules.dsl import ChangeIntent

        analysis = (
            self.db.query(TicketAnalysis)
            .filter(TicketAnalysis.ticket_id == ticket.id)
            .order_by(TicketAnalysis.created_at.desc())
            .first()
        )
        intent = ChangeIntent.model_validate_json(analysis.structured_output) if analysis else ChangeIntent(
            change_type="TEXT_STRING_UPDATE", intent="RERUN"
        )
        self._run_tests(ticket, proposal, rule, body, intent, skip_transition=True)

    def _run_validation(  # returns False when blocked
        self,
        ticket: Ticket,
        proposal: ChangeProposal,
        body: dict,
        intent: Any,
        deps: list,
        inheritances: list,
        resolution: Any,
        skip_transition: bool = False,
    ) -> bool:
        if not skip_transition:
            transition(ticket, WorkflowState.VALIDATING)
        self.emit(ticket, "VALIDATION_STARTED", "Validation started")
        citations = {c.citation_id: c.status for c in self.db.query(ScientificCitation).all()}
        ctx = {
            "known_citation_ids": list(citations.keys()),
            "citation_statuses": citations,
            "expected_market": intent.market.value,
            "dependencies": [d["depends_on_rule_id"] for d in deps if d["rule_id"] == proposal.target_rule_id],
            "inherited_rule_ids": resolution.inherited_rule_ids,
        }
        results = run_validators(body, ctx)
        blocking = is_blocking(results)
        run = ValidationRun(
            proposal_id=proposal.id,
            ticket_id=ticket.id,
            overall_status="FAIL" if blocking else "PASS",
            blocking=blocking,
            summary="Blocking validation failed" if blocking else "All blocking validators passed",
        )
        self.db.add(run)
        self.db.flush()
        for r in results:
            self.db.add(
                ValidationResult(
                    run_id=run.id,
                    validator_name=r.validator_name,
                    status=r.status,
                    severity=r.severity,
                    message=r.message,
                    evidence=json.dumps(r.evidence),
                    timestamp=r.timestamp,
                )
            )
            self.emit(ticket, "VALIDATOR_RESULT", f"{r.validator_name} {r.status}")
        if blocking:
            if not skip_transition:
                transition(ticket, WorkflowState.VALIDATION_FAILED)
            ticket.processing_lock = 0
            self.emit(ticket, "VALIDATION_FAILED", "Validation failed")
            return False
        self.emit(ticket, "VALIDATION_COMPLETED", "Validation completed")
        self.audit.record(
            event_type="VALIDATION_COMPLETED",
            entity_type="validation_run",
            entity_id=run.id,
            ticket_id=ticket.id,
            new_state={"status": "PASS"},
        )
        return True

    def _run_tests(
        self,
        ticket: Ticket,
        proposal: ChangeProposal,
        rule: RuleDefinition,
        proposed_body: dict,
        intent: Any,
        skip_transition: bool = False,
    ) -> None:
        if not skip_transition:
            transition(ticket, WorkflowState.SANDBOXING)
        self.emit(ticket, "SANDBOX_CREATED", "Sandbox prepared")
        if not skip_transition:
            transition(ticket, WorkflowState.TESTING)
        self.emit(ticket, "HISTORICAL_REPLAY_STARTED", "Historical review replay executing")

        reviews = self.db.query(HistoricalReview).all()
        review_dicts = [
            {
                "review_id": r.review_id,
                "market": r.market,
                "brand": r.brand,
                "therapeutic_area": r.therapeutic_area,
                "language": r.language,
                "material_type": r.material_type,
                "content": r.content,
                "expected_flags": json.loads(r.expected_flags or "[]"),
            }
            for r in reviews
        ]
        prod_rules = self._production_rule_bodies()
        session = SandboxSession(
            production_rules=prod_rules,
            proposed_override=proposed_body,
            target_rule_id=rule.rule_id,
        )
        start = datetime.now(UTC)
        scope = {
            "market": intent.market.value,
            "brand": intent.brand.value,
            "therapeutic_area": intent.therapeutic_area.value,
        }
        report = RegressionEngine().run(session, review_dicts, scope)
        duration = int((datetime.now(UTC) - start).total_seconds() * 1000)

        run = TestRun(
            proposal_id=proposal.id,
            ticket_id=ticket.id,
            status="COMPLETED",
            total_cases=report.total_cases,
            unchanged_cases=report.unchanged_cases,
            intentionally_changed_cases=report.intentionally_changed_cases,
            unexpected_changed_cases=report.unexpected_changed_cases,
            new_false_positives=report.new_false_positives,
            new_false_negatives=report.new_false_negatives,
            baseline_flag_rate=report.baseline_flag_rate,
            proposed_flag_rate=report.proposed_flag_rate,
            flag_rate_delta=report.flag_rate_delta,
            duration_ms=duration,
            regression_safety=report.regression_safety,
            summary=json.dumps(report.as_dict()),
        )
        self.db.add(run)
        self.db.flush()
        # Persist a representative subset plus all non-unchanged cases
        persisted = 0
        for result in report.results:
            if result.classification == "UNCHANGED" and persisted > 40:
                continue
            self.db.add(
                TestResult(
                    run_id=run.id,
                    review_id=result.review_id,
                    classification=result.classification,
                    baseline_flags=json.dumps(result.baseline_flags),
                    proposed_flags=json.dumps(result.proposed_flags),
                    baseline_route=result.baseline_route,
                    proposed_route=result.proposed_route,
                    notes=result.notes,
                )
            )
            persisted += 1

        self.emit(
            ticket,
            "REGRESSION_COMPLETED",
            f"Regression completed — {report.total_cases} reviews",
            report.as_dict(),
        )
        self.audit.record(
            event_type="REGRESSION_COMPLETED",
            entity_type="test_run",
            entity_id=run.id,
            ticket_id=ticket.id,
            new_state=report.as_dict(),
        )
        if report.regression_safety == "FAIL" and report.unexpected_changed_cases > 80:
            if not skip_transition:
                transition(ticket, WorkflowState.REGRESSION_FAILED)
            ticket.processing_lock = 0
            self.emit(ticket, "REGRESSION_FAILED", "Regression safety failed")
            return

        if not skip_transition:
            transition(ticket, WorkflowState.IMPACT_ANALYSIS)
        dep_count = (
            self.db.query(RuleDependency).filter(RuleDependency.rule_id == rule.id).count()
        )
        impact = ImpactAnalyzer().analyze(scope, report.results, review_dicts, dep_count, 1)
        ia = ImpactAnalysis(
            proposal_id=proposal.id,
            ticket_id=ticket.id,
            modified_rules=impact.modified_rules,
            markets_affected=json.dumps(impact.markets_affected),
            brands_affected=json.dumps(impact.brands_affected),
            material_types_affected=json.dumps(impact.material_types_affected),
            dependent_rules_inspected=impact.dependent_rules_inspected,
            historical_records_affected=impact.historical_records_affected,
            unrelated_markets_impacted=impact.unrelated_markets_impacted,
            unrelated_brands_impacted=impact.unrelated_brands_impacted,
            summary_json=json.dumps(impact.as_dict()),
        )
        self.db.add(ia)
        self.emit(ticket, "IMPACT_COMPLETED", "Impact analysis completed", impact.as_dict())
        self.audit.record(
            event_type="IMPACT_COMPLETED",
            entity_type="impact_analysis",
            entity_id=ia.id,
            ticket_id=ticket.id,
            new_state=impact.as_dict(),
        )

        if not skip_transition:
            transition(ticket, WorkflowState.RISK_ASSESSMENT)
        citation_unverified = False
        for ref in proposed_body.get("references", []):
            cid = ref.get("id") if isinstance(ref, dict) else ref
            cit = self.db.query(ScientificCitation).filter(ScientificCitation.citation_id == cid).one_or_none()
            if cit and cit.status == "CITATION_VERIFICATION_REQUIRED":
                citation_unverified = True
        risk = RiskEngine().assess(
            category=intent.rule_category.value,
            scope_type=rule.scopes[0].scope_type if rule.scopes else "MARKET_BRAND",
            markets=impact.markets_affected,
            brands=impact.brands_affected,
            regression_safety=report.regression_safety,
            unexpected_changes=report.unexpected_changed_cases,
            false_positives=report.new_false_positives,
            false_negatives=report.new_false_negatives,
            citation_unverified=citation_unverified,
            flag_rate_delta=report.flag_rate_delta,
            scientific=True,
        )
        provider = get_llm_provider()
        ai_summary = provider.summarize_impact(impact.as_dict(), risk.as_dict())
        ra = RiskAssessment(
            proposal_id=proposal.id,
            ticket_id=ticket.id,
            overall_level=risk.overall,
            dimensions_json=json.dumps(risk.dimensions),
            rationale=risk.rationale,
            policy_gate=risk.policy_gate,
            ai_summary=ai_summary,
        )
        self.db.add(ra)
        ticket.risk_level = risk.overall
        self.emit(ticket, "RISK_CALCULATED", f"Risk assessment {risk.overall}", risk.as_dict())
        self.audit.record(
            event_type="RISK_CALCULATED",
            entity_type="risk_assessment",
            entity_id=ra.id,
            ticket_id=ticket.id,
            new_state=risk.as_dict(),
        )

        if skip_transition:
            return

        policy = ApprovalPolicyEngine().resolve(
            category=intent.rule_category.value,
            scope_type=rule.scopes[0].scope_type if rule.scopes else "MARKET_BRAND",
            risk=risk.overall,
            citation_unverified=citation_unverified,
        )
        req = ApprovalRequest(
            proposal_id=proposal.id,
            ticket_id=ticket.id,
            required_roles=json.dumps(policy.required_roles),
            status="PENDING",
            risk_level_at_request=risk.overall,
            proposal_checksum=proposal.proposed_checksum,
        )
        self.db.add(req)
        transition(ticket, WorkflowState.AWAITING_APPROVAL)
        self.emit(ticket, "APPROVAL_REQUESTED", "Awaiting human approval", {"roles": policy.required_roles})
        self.audit.record(
            event_type="APPROVAL_REQUESTED",
            entity_type="approval_request",
            entity_id=req.id,
            ticket_id=ticket.id,
            new_state={"roles": policy.required_roles, "risk": risk.overall},
        )

    def _load_rule_dicts(self) -> list[dict[str, Any]]:
        rows = (
            self.db.query(RuleDefinition, RuleScope)
            .join(RuleScope, RuleScope.rule_id == RuleDefinition.id)
            .filter(RuleDefinition.status == "ACTIVE")
            .all()
        )
        out = []
        for rule, scope in rows:
            out.append(
                {
                    "id": rule.id,
                    "rule_id": rule.rule_id,
                    "name": rule.name,
                    "status": rule.status,
                    "priority": rule.priority,
                    "rule_category": rule.rule_category,
                    "scope_type": scope.scope_type,
                    "market": scope.market,
                    "brand": scope.brand,
                    "therapeutic_area": scope.therapeutic_area,
                    "material_type": scope.material_type,
                }
            )
        return out

    def _production_rule_bodies(self) -> list[dict[str, Any]]:
        rules = self.db.query(RuleDefinition).filter(RuleDefinition.status == "ACTIVE").all()
        bodies = []
        for rule in rules:
            if not rule.production_version_id:
                continue
            ver = self.db.get(RuleVersion, rule.production_version_id)
            if ver:
                bodies.append(json.loads(ver.body_json))
        return bodies

    def _sources_for(self, ticket: Ticket, intent: Any) -> list[dict[str, Any]]:
        sources = [
            {
                "source_identifier": ticket.ticket_number,
                "source_type": "ticket",
                "why_relevant": "Primary natural-language request",
                "retrieval_score": 1.0,
                "snippet": ticket.description[:280],
            }
        ]
        if intent.citation_to_remove:
            sources.append(
                {
                    "source_identifier": intent.citation_to_remove,
                    "source_type": "scientific_citation",
                    "why_relevant": "Citation requested for removal",
                    "retrieval_score": 0.95,
                    "snippet": "Synthetic Demo Dataset citation record",
                }
            )
        if intent.citation_to_add:
            sources.append(
                {
                    "source_identifier": intent.citation_to_add,
                    "source_type": "scientific_citation",
                    "why_relevant": "Citation requested for addition",
                    "retrieval_score": 0.96,
                    "snippet": "Synthetic Demo Dataset citation record",
                }
            )
        return sources
