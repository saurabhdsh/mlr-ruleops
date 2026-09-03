from __future__ import annotations

import json

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("workflow.events")

CHANNEL_PREFIX = "ruleops.ticket."


def publish_ticket_event(ticket_id: str, payload: dict) -> None:
    try:
        import redis

        client = redis.from_url(settings.redis_url, socket_connect_timeout=0.4)
        client.publish(f"{CHANNEL_PREFIX}{ticket_id}", json.dumps(payload))
        client.publish("ruleops.events", json.dumps({"ticket_id": ticket_id, **payload}))
    except Exception as exc:
        logger.info("event_publish_skipped", error=str(exc))
