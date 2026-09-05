from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import ValidationError

from app.ai.fallback import DeterministicFallbackProvider
from app.ai.provider import LLMProvider
from app.core.config import settings
from app.core.logging import get_logger
from app.rules.dsl import ChangeIntent, ChangeProposalPayload
from app.rules.mutation import RuleMutationEngine

logger = get_logger("ai.remote")

SYSTEM_PROMPT = """You are an MLR RuleOps interpretation service.
Extract a structured change intent from a regulatory operations ticket.
Return ONLY valid JSON matching the schema. Do not invent citations, markets, or brands.
If a high-risk field is unknown, set value to null and lower confidence.
Never include chain-of-thought. Provide a short business decision_summary only.
Schema version: change-intent-v1

Each of market, brand, therapeutic_area, language, material_type, rule_category, string_type MUST be an object:
{"value": string|null, "confidence": number}

Required top-level keys:
change_type, intent, market, brand, therapeutic_area, language, material_type, rule_category, string_type,
operation, citation_to_remove, citation_to_add, overall_confidence, decision_summary
string_type value is one of DISCLAIMER, PI_LINK, CLAIM, LEGAL_FOOTER, ROUTING.
"""

PROPOSE_PROMPT = """You are an MLR RuleOps mutation planner.
Given a validated change intent and the current rule JSON body, return ONLY JSON:
{
  "change_type": string,
  "target_rule_id": string,
  "operations": [{"operation": "REMOVE_REFERENCE"|"ADD_REFERENCE"|"REPLACE_TEXT"|"CHANGE_ROUTE"|"ADD_FLAG"|"REMOVE_FLAG"|"SET_FIELD", "value": any, "path": string|null}],
  "reason": string
}
Rules:
- Never invent citation IDs. Use only citation_to_remove / citation_to_add from the intent.
- For TEXT disclaimer citation swaps: REMOVE_REFERENCE old, ADD_REFERENCE new, REPLACE_TEXT with updated content that mentions the new year/citation and removes the old.
- Do not change market, brand, or therapeutic_area unless the intent explicitly requires it.
- Operations must be executable against the provided current body.
"""

IMPACT_PROMPT = """Write a 2-4 sentence operational summary of this MLR rule-change impact and risk for a human approver.
No markdown. Do not invent numbers — use only values present in the JSON.
"""

INTENT_OBJECT_FIELDS = (
    "market",
    "brand",
    "therapeutic_area",
    "language",
    "material_type",
    "rule_category",
    "string_type",
)


def _strip_fences(raw: str) -> str:
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return cleaned.strip()


def _coerce_intent_payload(data: dict[str, Any]) -> dict[str, Any]:
    for key in INTENT_OBJECT_FIELDS:
        value = data.get(key)
        if isinstance(value, str) or value is None:
            data[key] = {"value": value, "confidence": 0.8 if value else 0.0}
        elif isinstance(value, dict) and "value" not in value:
            data[key] = {"value": value.get("name") or value.get("id"), "confidence": float(value.get("confidence") or 0.5)}
    return data


def _parse_intent(raw: str) -> ChangeIntent:
    data = json.loads(_strip_fences(raw))
    if not isinstance(data, dict):
        raise json.JSONDecodeError("intent must be an object", raw, 0)
    return ChangeIntent.model_validate(_coerce_intent_payload(data))


def _body_satisfies_intent(body: dict[str, Any], intent: ChangeIntent) -> bool:
    refs = [r.get("id") if isinstance(r, dict) else r for r in body.get("references", [])]
    if intent.citation_to_add and intent.citation_to_add not in refs:
        return False
    if intent.citation_to_remove and intent.citation_to_remove in refs:
        return False
    return True


def _parse_proposal(raw: str, current_body: dict[str, Any], intent: ChangeIntent) -> dict[str, Any]:
    data = json.loads(_strip_fences(raw))
    if not isinstance(data, dict):
        raise json.JSONDecodeError("proposal must be an object", raw, 0)
    data.setdefault("change_type", intent.change_type)
    data.setdefault("target_rule_id", current_body.get("rule_id") or "")
    data.setdefault("reason", intent.decision_summary or intent.business_reason)
    payload = ChangeProposalPayload.model_validate(data)
    if not payload.operations:
        raise ValueError("proposal contained no operations")
    dumped = payload.model_dump()
    mutated = RuleMutationEngine().apply(current_body, dumped["operations"])
    if not _body_satisfies_intent(mutated.proposed_body, intent):
        raise ValueError("proposal operations do not realize the extracted citation or field intent")
    return dumped


CompleteFn = Callable[[str, str], str]


def _propose_with_llm(
    complete: CompleteFn,
    intent: ChangeIntent,
    current_body: dict[str, Any],
    fallback: DeterministicFallbackProvider,
) -> dict[str, Any]:
    user = json.dumps({"intent": intent.model_dump(), "current_body": current_body})
    try:
        return _parse_proposal(complete(PROPOSE_PROMPT, user), current_body, intent)
    except (ValidationError, json.JSONDecodeError, ValueError, Exception) as exc:
        logger.warning("llm_propose_failed_repair", error=str(exc)[:240])
        try:
            repaired = complete(PROPOSE_PROMPT + " Repair to valid JSON only. No prose.", user)
            return _parse_proposal(repaired, current_body, intent)
        except Exception:
            logger.warning("llm_propose_failed_fallback")
            return fallback.propose_change(intent, current_body)


def _summarize_with_llm(
    complete: CompleteFn,
    impact: dict[str, Any],
    risk: dict[str, Any],
    fallback: DeterministicFallbackProvider,
) -> str:
    user = json.dumps({"impact": impact, "risk": risk})
    try:
        text = complete(IMPACT_PROMPT, user).strip()
        if not text:
            raise ValueError("empty summary")
        return text[:2000]
    except Exception as exc:
        logger.warning("llm_summarize_failed_fallback", error=str(exc)[:240])
        return fallback.summarize_impact(impact, risk)


class OpenAIProvider(LLMProvider):
    name = "openai"
    model = settings.openai_model
    is_local_fallback = False

    def __init__(self) -> None:
        from openai import OpenAI

        self.client = OpenAI(api_key=settings.openai_api_key)
        self.fallback = DeterministicFallbackProvider()

    def _complete(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    def _complete_text(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    def interpret_ticket(self, title: str, description: str, hints: dict[str, Any]) -> ChangeIntent:
        user = json.dumps({"title": title, "description": description, "hints": hints})
        try:
            return _parse_intent(self._complete(SYSTEM_PROMPT, user))
        except (ValidationError, json.JSONDecodeError, Exception) as exc:
            logger.warning("openai_interpret_failed_using_repair", error=str(exc))
            try:
                return _parse_intent(self._complete(SYSTEM_PROMPT + " Repair to valid JSON only.", user))
            except Exception:
                logger.warning("openai_repair_failed_fallback")
                return self.fallback.interpret_ticket(title, description, hints)

    def rank_rule_candidates(self, intent: ChangeIntent, candidates: list[dict[str, Any]]) -> list[str]:
        return self.fallback.rank_rule_candidates(intent, candidates)

    def propose_change(self, intent: ChangeIntent, current_body: dict[str, Any]) -> dict[str, Any]:
        return _propose_with_llm(self._complete, intent, current_body, self.fallback)

    def summarize_impact(self, impact: dict[str, Any], risk: dict[str, Any]) -> str:
        return _summarize_with_llm(self._complete_text, impact, risk, self.fallback)


class AzureOpenAIProvider(OpenAIProvider):
    name = "azure_openai"

    def __init__(self) -> None:
        from openai import AzureOpenAI

        self.client = AzureOpenAI(
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_endpoint=settings.azure_openai_endpoint,
        )
        self.model = settings.azure_openai_deployment
        self.fallback = DeterministicFallbackProvider()


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    model = settings.anthropic_model
    is_local_fallback = False

    def __init__(self) -> None:
        import anthropic

        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.fallback = DeterministicFallbackProvider()

    def _complete(self, system: str, user: str) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1800,
            temperature=0,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text if resp.content else ""

    def interpret_ticket(self, title: str, description: str, hints: dict[str, Any]) -> ChangeIntent:
        user = json.dumps({"title": title, "description": description, "hints": hints})
        try:
            return _parse_intent(self._complete(SYSTEM_PROMPT, user))
        except Exception as exc:
            logger.warning("anthropic_interpret_failed_fallback", error=str(exc))
            return self.fallback.interpret_ticket(title, description, hints)

    def rank_rule_candidates(self, intent: ChangeIntent, candidates: list[dict[str, Any]]) -> list[str]:
        return self.fallback.rank_rule_candidates(intent, candidates)

    def propose_change(self, intent: ChangeIntent, current_body: dict[str, Any]) -> dict[str, Any]:
        return _propose_with_llm(self._complete, intent, current_body, self.fallback)

    def summarize_impact(self, impact: dict[str, Any], risk: dict[str, Any]) -> str:
        return _summarize_with_llm(self._complete, impact, risk, self.fallback)
