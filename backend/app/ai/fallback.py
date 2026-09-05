from __future__ import annotations

import re
from typing import Any

from app.rules.dsl import ChangeIntent, ChangeIntentField
from app.ai.provider import LLMProvider

MARKETS = ["US", "UK", "DE", "FR", "ES", "IT", "JP", "AU", "CA", "BR", "LATAM", "MX"]
BRANDS = ["Drug A", "Drug B", "Drug C", "Drug X", "Trelegy", "Jemperli", "Nucala", "Blenrep", "Shingrix", "Benlysta"]
AREAS = ["Cardiovascular", "Respiratory", "Oncology", "Immunology", "Vaccines"]
MATERIALS = [
    "Promotional",
    "Medical Communication",
    "Scientific Response",
    "Digital Advertisement",
    "Detail Aid",
    "Email",
    "Website",
]


def _field(value: str | None, confidence: float) -> ChangeIntentField:
    return ChangeIntentField(value=value, confidence=confidence if value else 0.0)


class DeterministicFallbackProvider(LLMProvider):
    name = "deterministic"
    model = "local-deterministic-parser"
    is_local_fallback = True

    def interpret_ticket(self, title: str, description: str, hints: dict[str, Any]) -> ChangeIntent:
        text = f"{title}\n{description}"
        lower = text.lower()

        market = hints.get("market") or _find_market(text)
        brand = hints.get("brand") or _find_brand(text)
        area = hints.get("therapeutic_area") or _find_area(text)
        material = hints.get("material_type") or _find_material(text) or "Promotional"
        language = hints.get("language") or "EN"

        is_logic = bool(
            re.search(r"\bif\b.+\broute\b|\bflag constraint\b|\bbusiness logic\b", lower)
        )
        change_type = "BUSINESS_LOGIC_CHANGE" if is_logic else "TEXT_STRING_UPDATE"

        citation_remove = None
        citation_add = None
        if "2020" in lower and ("remove" in lower or "replace" in lower):
            citation_remove = "CIT-2020-001"
        if "2026" in lower and ("include" in lower or "add" in lower or "new" in lower):
            citation_add = "CIT-2026-004"

        intent_name = "UPDATE_DISCLAIMER" if "disclaimer" in lower else "UPDATE_RULE"
        operation = "REPLACE_REFERENCE" if citation_remove or citation_add else "REPLACE_TEXT"
        category = "DISCLAIMER" if "disclaimer" in lower else "GENERAL"
        if "disclaimer" in lower:
            string_type = "DISCLAIMER"
        elif "hyperlink" in lower or "prescribing-information" in lower or "pi link" in lower:
            string_type = "PI_LINK"
        elif "route" in lower or is_logic:
            string_type = "ROUTING"
        elif "legal" in lower or "footer" in lower:
            string_type = "LEGAL_FOOTER"
        elif "claim" in lower:
            string_type = "CLAIM"
        else:
            string_type = category if category != "GENERAL" else "DISCLAIMER"

        routing_target = None
        constraint = None
        route_m = re.search(r"route to ([A-Za-z0-9 .'-]+)", description, re.I)
        if route_m:
            routing_target = route_m.group(1).strip(" .")
            change_type = "BUSINESS_LOGIC_CHANGE"
            intent_name = "UPDATE_ROUTING"
            operation = "CHANGE_ROUTE"
        flag_m = re.search(r"flag(?:\s+constraint)?\s+([A-Za-z0-9 .'-]+)", description, re.I)
        if flag_m:
            constraint = flag_m.group(1).strip(" .")

        risk_indicators = []
        if citation_add or citation_remove:
            risk_indicators.append("scientific_citation_change")
        if change_type == "BUSINESS_LOGIC_CHANGE":
            risk_indicators.append("routing_logic")

        ambiguities = []
        if not market:
            ambiguities.append("market")
        if not brand:
            ambiguities.append("brand")

        confidences = [
            0.99 if market else 0.0,
            0.99 if brand else 0.0,
            0.97 if area else 0.4,
        ]
        overall = sum(confidences) / len(confidences)

        summary = (
            f"Local deterministic interpretation: {change_type} / {intent_name} "
            f"for {brand or 'unspecified brand'} in {market or 'unspecified market'}."
        )
        if citation_remove or citation_add:
            summary += f" Replace {citation_remove or 'n/a'} with {citation_add or 'n/a'}."

        return ChangeIntent(
            change_type=change_type,
            intent=intent_name,
            market=_field(market, 0.99 if market else 0.0),
            brand=_field(brand, 0.99 if brand else 0.0),
            therapeutic_area=_field(area, 0.97 if area else 0.2),
            language=_field(language, 0.9),
            material_type=_field(material, 0.85 if material else 0.4),
            rule_category=_field(category, 0.93 if category == "DISCLAIMER" else 0.6),
            string_type=_field(string_type, 0.93),
            old_value="CIT-2020-001" if citation_remove else None,
            new_value="CIT-2026-004" if citation_add else None,
            operation=operation,
            citation_to_remove=citation_remove,
            citation_to_add=citation_add,
            remove_reference="2020 study" if citation_remove else None,
            add_reference="2026 clinical trial" if citation_add else None,
            routing_target=routing_target,
            constraint=constraint,
            business_reason=title,
            risk_indicators=risk_indicators,
            ambiguities=ambiguities,
            requires_scientific_verification=bool(citation_add),
            overall_confidence=round(overall, 4),
            decision_summary=summary,
        )

    def rank_rule_candidates(self, intent: ChangeIntent, candidates: list[dict[str, Any]]) -> list[str]:
        return [c.get("rule_id", "") for c in candidates]

    def propose_change(self, intent: ChangeIntent, current_body: dict[str, Any]) -> dict[str, Any]:
        ops = []
        if intent.citation_to_remove:
            ops.append({"operation": "REMOVE_REFERENCE", "value": intent.citation_to_remove})
        if intent.citation_to_add:
            ops.append({"operation": "ADD_REFERENCE", "value": intent.citation_to_add})
        if intent.citation_to_add and current_body.get("rule_type") == "TEXT":
            content = current_body.get("content", "")
            content = re.sub(r"20\d{2}", "2026", content, count=1)
            content = content.replace("CIT-2020-001", intent.citation_to_add)
            if "2026" not in content:
                content = content.rstrip(".") + " Includes 2026 clinical trial evidence."
            # Prefer explicit rewrite for the demo disclaimer
            if "CIT-2020-001" in (current_body.get("content") or "") or "2020" in (current_body.get("content") or ""):
                content = (
                    "Drug A (generic name) is indicated to reduce cardiovascular risk in appropriate adults. "
                    "This promotional claim is supported by Chen et al., 2026 (CIT-2026-004), "
                    "a randomized controlled outcomes trial. See full prescribing information. "
                    "[Synthetic Demo Dataset — citation metadata is synthetic.]"
                )
            ops.append({"operation": "REPLACE_TEXT", "value": content})
        if intent.routing_target:
            ops.append({"operation": "CHANGE_ROUTE", "value": intent.routing_target})
        if intent.constraint:
            ops.append({"operation": "ADD_FLAG", "value": intent.constraint})
        if not ops:
            ops.append({"operation": "SET_FIELD", "path": "content", "value": current_body.get("content", "")})
        return {
            "change_type": intent.change_type,
            "target_rule_id": current_body.get("rule_id", ""),
            "operations": ops,
            "reason": intent.business_reason or intent.decision_summary,
        }

    def summarize_impact(self, impact: dict[str, Any], risk: dict[str, Any]) -> str:
        return (
            f"Local summary: {impact.get('modified_rules', 1)} rule(s) modified; "
            f"{impact.get('historical_records_affected', 0)} historical reviews impacted; "
            f"overall risk {risk.get('overall', 'UNKNOWN')}."
        )


def _find_market(text: str) -> str | None:
    if re.search(r"\blatam\b|\blatin america\b", text, re.I):
        return "LATAM"
    if re.search(r"\bbrazil\b|\bbrasil\b|\bBR\b", text, re.I):
        return "BR"
    if re.search(r"\bgermany\b|\bdeutschland\b|\bDE\b", text, re.I):
        return "DE"
    if re.search(r"\bfrance\b|\bFR\b", text, re.I):
        return "FR"
    if re.search(r"\bunited states\b|\bU\.S\.\b|\bUS\b", text, re.I):
        return "US"
    for m in MARKETS:
        if re.search(rf"\b{m}\b", text, re.I):
            return m
    return None


def _find_brand(text: str) -> str | None:
    for b in BRANDS:
        if re.search(rf"\b{re.escape(b)}\b", text, re.I):
            return b
    return None


def _find_area(text: str) -> str | None:
    for a in AREAS:
        if re.search(rf"\b{re.escape(a)}\b", text, re.I):
            return a
    if re.search(r"\bcardiovascular\b|\bcardiology\b", text, re.I):
        return "Cardiovascular"
    return None


def _find_material(text: str) -> str | None:
    for m in MATERIALS:
        if m.lower() in text.lower():
            return m
    return None
