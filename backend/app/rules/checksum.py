import hashlib
import json
from typing import Any


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def rule_checksum(payload: Any) -> str:
    if isinstance(payload, str):
        raw = payload
    else:
        raw = canonical_json(payload)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
