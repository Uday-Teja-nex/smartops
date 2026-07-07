"""Realtime event fanout via Redis pub/sub.

The API publishes granular events whenever incidents or sources change;
the SSE endpoint subscribes and forwards them to connected UIs. Publishing
is best-effort: REST + Postgres remain the source of truth, so a Redis
hiccup never fails a write.
"""

from __future__ import annotations

import json
from typing import Any

from redis import Redis

from app.config import get_settings

settings = get_settings()
EVENTS_CHANNEL = "smartops:events"

_redis: Redis | None = None


def _client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def publish_event(kind: str, data: dict[str, Any]) -> None:
    """kind: 'incident' | 'source' (extend as new streams appear)."""
    try:
        _client().publish(EVENTS_CHANNEL, json.dumps({"kind": kind, "data": data}, default=str))
    except Exception:  # noqa: BLE001 - realtime is best-effort by design.
        pass
