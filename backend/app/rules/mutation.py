from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from typing import Any

from app.core.enums import MutationOp
from app.core.errors import ValidationFailed
from app.rules.checksum import rule_checksum
from app.rules.dsl import MutationOperation, parse_rule_body


@dataclass
class MutationResult:
    proposed_body: dict[str, Any]
    checksum: str
    diff: dict[str, Any]
    base_checksum: str


class RuleMutationEngine:
    """Applies typed operations to a specific base version. Never writes production."""

    def apply(
        self,
        base_body: dict[str, Any] | str,
        operations: list[MutationOperation | dict[str, Any]],
        expected_base_checksum: str | None = None,
    ) -> MutationResult:
        body = json.loads(base_body) if isinstance(base_body, str) else copy.deepcopy(base_body)
        base_checksum = rule_checksum(body)
        if expected_base_checksum and expected_base_checksum != base_checksum:
            raise ValidationFailed(
                "Base version checksum mismatch — proposal is stale",
                {"expected": expected_base_checksum, "actual": base_checksum},
            )
        # Preconditions: body must parse
        parse_rule_body(body)

        ops = [
            o if isinstance(o, MutationOperation) else MutationOperation.model_validate(o)
            for o in operations
        ]
        for op in ops:
            self._apply_one(body, op)

        parse_rule_body(body)
        proposed_checksum = rule_checksum(body)
        return MutationResult(
            proposed_body=body,
            checksum=proposed_checksum,
            diff=semantic_diff(json.loads(base_body) if isinstance(base_body, str) else base_body, body),
            base_checksum=base_checksum,
        )

    def _apply_one(self, body: dict[str, Any], op: MutationOperation) -> None:
        name = op.operation
        if name in {MutationOp.REPLACE_TEXT, "REPLACE_TEXT", "replace_text"}:
            body["content"] = op.value
        elif name in {MutationOp.ADD_REFERENCE, "ADD_REFERENCE", "add_reference"}:
            refs = body.setdefault("references", [])
            cid = op.value if isinstance(op.value, str) else op.value.get("id")
            if not any((r.get("id") if isinstance(r, dict) else r) == cid for r in refs):
                refs.append({"type": "scientific_citation", "id": cid})
        elif name in {MutationOp.REMOVE_REFERENCE, "REMOVE_REFERENCE", "remove_reference"}:
            cid = op.value if isinstance(op.value, str) else (op.value or {}).get("id")
            body["references"] = [
                r
                for r in body.get("references", [])
                if (r.get("id") if isinstance(r, dict) else r) != cid
            ]
        elif name in {MutationOp.SET_FIELD, "SET_FIELD", "set_field"}:
            path = op.path or "content"
            body[path] = op.value
        elif name in {MutationOp.ADD_CONDITION, "ADD_CONDITION", "add_condition"}:
            when = body.setdefault("when", {"all": []})
            bucket = when.get("all") or when.get("any")
            if bucket is None:
                when["all"] = [op.value]
            else:
                bucket.append(op.value)
        elif name in {MutationOp.REMOVE_CONDITION, "REMOVE_CONDITION", "remove_condition"}:
            self._remove_condition(body.get("when", {}), op.value)
        elif name in {MutationOp.MODIFY_CONDITION, "MODIFY_CONDITION", "modify_condition"}:
            self._modify_condition(body.get("when", {}), op.old_value, op.value)
        elif name in {MutationOp.ADD_ACTION, "ADD_ACTION", "add_action"}:
            body.setdefault("actions", []).append(op.value)
        elif name in {MutationOp.REMOVE_ACTION, "REMOVE_ACTION", "remove_action"}:
            body["actions"] = [a for a in body.get("actions", []) if a != op.value]
        elif name in {MutationOp.CHANGE_ROUTE, "CHANGE_ROUTE", "change_route"}:
            changed = False
            for action in body.get("actions", []):
                if action.get("type") == "route":
                    action["target"] = op.value
                    changed = True
            if not changed:
                body.setdefault("actions", []).append({"type": "route", "target": op.value})
        elif name in {MutationOp.ADD_FLAG, "ADD_FLAG", "add_flag"}:
            body.setdefault("actions", []).append({"type": "flag", "value": op.value})
        elif name in {MutationOp.REMOVE_FLAG, "REMOVE_FLAG", "remove_flag"}:
            body["actions"] = [
                a
                for a in body.get("actions", [])
                if not (a.get("type") == "flag" and a.get("value") == op.value)
            ]
        else:
            raise ValidationFailed(f"Unsupported mutation: {name}")


    def _remove_condition(self, node: Any, value: Any) -> None:
        if not isinstance(node, dict):
            return
        for key in ("all", "any"):
            items = node.get(key)
            if not items:
                continue
            node[key] = [i for i in items if i != value]

    def _modify_condition(self, node: Any, old: Any, new: Any) -> None:
        if not isinstance(node, dict):
            return
        for key in ("all", "any"):
            items = node.get(key) or []
            for i, item in enumerate(items):
                if item == old:
                    items[i] = new


def semantic_diff(current: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    removed_text = ""
    added_text = ""
    if current.get("content") != proposed.get("content"):
        removed_text = current.get("content") or ""
        added_text = proposed.get("content") or ""

    cur_refs = {r.get("id") if isinstance(r, dict) else r for r in current.get("references", [])}
    new_refs = {r.get("id") if isinstance(r, dict) else r for r in proposed.get("references", [])}

    return {
        "content_changed": current.get("content") != proposed.get("content"),
        "removed_text": removed_text,
        "added_text": added_text,
        "removed_references": sorted(cur_refs - new_refs),
        "added_references": sorted(new_refs - cur_refs),
        "changed_conditions": current.get("when") != proposed.get("when"),
        "current_when": current.get("when"),
        "proposed_when": proposed.get("when"),
        "changed_actions": current.get("actions") != proposed.get("actions"),
        "current_actions": current.get("actions"),
        "proposed_actions": proposed.get("actions"),
        "current": current,
        "proposed": proposed,
    }
