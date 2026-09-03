from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.rules.dsl import ChangeIntent


class LLMProvider(ABC):
    name: str
    model: str
    is_local_fallback: bool = False

    @abstractmethod
    def interpret_ticket(self, title: str, description: str, hints: dict[str, Any]) -> ChangeIntent:
        raise NotImplementedError

    @abstractmethod
    def rank_rule_candidates(self, intent: ChangeIntent, candidates: list[dict[str, Any]]) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def propose_change(self, intent: ChangeIntent, current_body: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def summarize_impact(self, impact: dict[str, Any], risk: dict[str, Any]) -> str:
        raise NotImplementedError
