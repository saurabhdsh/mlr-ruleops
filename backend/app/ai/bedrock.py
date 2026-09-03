from __future__ import annotations

import json
from typing import Any

from app.ai.fallback import DeterministicFallbackProvider
from app.ai.provider import LLMProvider
from app.ai.remote import (
    IMPACT_PROMPT,
    SYSTEM_PROMPT,
    _parse_intent,
    _propose_with_llm,
    _summarize_with_llm,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.rules.dsl import ChangeIntent

logger = get_logger("ai.bedrock")


def aws_session():
    """Same credential chain as aws_agent.py: AWS CLI profile, then default chain. No API keys."""
    import boto3

    region = settings.aws_region or "us-east-1"
    profile = (settings.aws_profile or "").strip()
    if profile:
        return boto3.Session(profile_name=profile, region_name=region)
    return boto3.Session(region_name=region)


def _converse_text(runtime, model_id: str, system: str, user: str, max_tokens: int = 1800) -> str:
    kwargs: dict[str, Any] = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": user}]}],
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0},
    }
    if system:
        kwargs["system"] = [{"text": system}]
    response = runtime.converse(**kwargs)
    output = response.get("output") or {}
    for block in output.get("message", {}).get("content", []):
        if "text" in block:
            return (block["text"] or "").strip()
    return ""


class BedrockProvider(LLMProvider):
    """Claude (or other Bedrock models) via IAM / AWS CLI. No Anthropic or OpenAI API keys."""

    name = "bedrock"
    is_local_fallback = False

    def __init__(self) -> None:
        self.model = settings.bedrock_model
        self.fallback = DeterministicFallbackProvider()
        session = aws_session()
        self.runtime = session.client("bedrock-runtime")
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        logger.info(
            "bedrock_session_ready",
            model=self.model,
            region=settings.aws_region,
            profile=settings.aws_profile or "default-chain",
            account=identity.get("Account"),
            arn=identity.get("Arn"),
        )

    def _complete(self, system: str, user: str) -> str:
        return _converse_text(self.runtime, self.model, system, user)

    def interpret_ticket(self, title: str, description: str, hints: dict[str, Any]) -> ChangeIntent:
        user = json.dumps({"title": title, "description": description, "hints": hints})
        try:
            return _parse_intent(self._complete(SYSTEM_PROMPT, user))
        except Exception as exc:
            logger.warning("bedrock_interpret_failed_repair", error=str(exc)[:240])
            try:
                return _parse_intent(self._complete(SYSTEM_PROMPT + " Repair to valid JSON only.", user))
            except Exception:
                logger.warning("bedrock_interpret_failed_fallback")
                return self.fallback.interpret_ticket(title, description, hints)

    def rank_rule_candidates(self, intent: ChangeIntent, candidates: list[dict[str, Any]]) -> list[str]:
        return self.fallback.rank_rule_candidates(intent, candidates)

    def propose_change(self, intent: ChangeIntent, current_body: dict[str, Any]) -> dict[str, Any]:
        return _propose_with_llm(self._complete, intent, current_body, self.fallback)

    def summarize_impact(self, impact: dict[str, Any], risk: dict[str, Any]) -> str:
        return _summarize_with_llm(self._complete, impact, risk, self.fallback)
