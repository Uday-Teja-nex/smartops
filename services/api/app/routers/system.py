"""What is up, what is down, and what that means for operators.

Every signed-in user may read this: the console uses it to show a degraded
banner naming the failed component. Probes run in parallel with short
timeouts, so a hung dependency costs at most about two seconds.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any, Callable

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth import Principal, require_viewer
from app.config import get_settings
from app.db import engine
from app.models import SourceModel
from app.tenancy import get_tenant_session

router = APIRouter(prefix="/v1/system", tags=["system"])
TIMEOUT = httpx.Timeout(2.0)
NOTIFIER_IMPACT = "Notifications are queued and send when it returns."


def component(cid: str, label: str, ok: bool, detail: str, impact: str) -> dict[str, Any]:
    return {"id": cid, "label": label, "ok": ok, "detail": detail, "impact": None if ok else impact}


def probe_database() -> dict[str, Any]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return component("database", "Database", True, "PostgreSQL answering", "")
    except Exception as exc:  # noqa: BLE001
        return component("database", "Database", False, f"unreachable ({type(exc).__name__})",
                         "Incidents and changes cannot be saved.")


def probe_redis_and_notifier() -> list[dict[str, Any]]:
    from redis import Redis

    from app.notifier import HEARTBEAT_KEY
    try:
        client = Redis.from_url(get_settings().redis_url, socket_timeout=2, socket_connect_timeout=2)
        client.ping()
        beat = client.get(HEARTBEAT_KEY)
    except Exception as exc:  # noqa: BLE001
        return [component("realtime", "Live updates", False, f"Redis unreachable ({type(exc).__name__})",
                          "Screens stop updating live and new sign-ins are paused."),
                component("notifier", "Notifications", False, "status unknown while Redis is down",
                          NOTIFIER_IMPACT)]
    realtime = component("realtime", "Live updates", True, "Redis answering", "")
    if beat is None:
        return [realtime, component("notifier", "Notifications", False, "no heartbeat in the last 15 s",
                                    NOTIFIER_IMPACT)]
    age = max(0.0, time.time() - float(beat))
    return [realtime, component("notifier", "Notifications", True, f"heartbeat {age:.0f} s ago", "")]


def probe_detector() -> dict[str, Any]:
    try:
        response = httpx.get(get_settings().detector_base_url + "/health", timeout=TIMEOUT)
        response.raise_for_status()
        body = response.json()
        return component("detector", "Object detection", True,
                         f"{body.get('backend', '?')} · {body.get('model', '?')}", "")
    except Exception as exc:  # noqa: BLE001
        return component("detector", "Object detection", False, f"unreachable ({type(exc).__name__})",
                         "Live detection is paused: no new incidents until it returns.")


def probe_ai() -> dict[str, Any]:
    impact = "Incidents still fire; their AI review will say unavailable."
    try:
        response = httpx.get(get_settings().orchestrator_base_url + "/v1/status", timeout=TIMEOUT)
        response.raise_for_status()
        body = response.json()
    except Exception as exc:  # noqa: BLE001
        return component("ai", "AI review", False, f"AI service unreachable ({type(exc).__name__})", impact)
    parts = [str(body.get("provider") or "?"), str(body.get("model") or "?"), str(body.get("detail") or "")]
    detail = " · ".join(part for part in parts if part)
    last = body.get("lastReview") or {}
    if last:
        detail += (f" · last review OK {last.get('secondsAgo')} s ago" if last.get("ok")
                   else f" · last review failed {last.get('secondsAgo')} s ago: {last.get('reason')}")
    return component("ai", "AI review", bool(body.get("ok")), detail, impact)


def stream_path(source: SourceModel) -> str | None:
    uri = source.source_uri.rstrip("/")
    return uri.rsplit("/", 1)[-1] if uri.startswith("rtsp://mediamtx") else None


def probe_streams(sources: list[SourceModel]) -> list[dict[str, Any]]:
    enabled = [source for source in sources if source.enabled and source.source_type == "rtsp"]
    if not enabled:
        return [component("streams", "Camera streams", True, "no enabled cameras", "")]
    try:
        response = httpx.get(get_settings().mediamtx_api_url + "/v3/paths/list", timeout=TIMEOUT)
        response.raise_for_status()
        ready = {item.get("name") for item in response.json().get("items", []) if item.get("ready")}
    except Exception as exc:  # noqa: BLE001
        return [component("streams", "Camera streams", False, f"stream server unreachable ({type(exc).__name__})",
                          "Live video and detection are paused for every camera.")]
    down = [s.name for s in enabled if stream_path(s) is not None and stream_path(s) not in ready]
    streams = component("streams", "Camera streams", not down,
                        f"{len(enabled) - len(down)}/{len(enabled)} enabled cameras publishing",
                        f"Not publishing: {', '.join(down)}.")
    now = datetime.now(UTC)
    stale = []
    for source in enabled:
        seen = (source.health or {}).get("lastSeen")
        try:
            age = (now - datetime.fromisoformat(str(seen))).total_seconds() if seen else None
        except ValueError:
            age = None
        if age is None or age > 20:
            stale.append(source.name)
    processor = component("processor", "Stream processing", not stale,
                          f"{len(enabled) - len(stale)}/{len(enabled)} cameras reporting in the last 20 s",
                          f"Live detection paused for: {', '.join(stale)}.")
    return [streams, processor]


@router.get("/status")
def system_status(session: Session = Depends(get_tenant_session),
                  principal: Principal = Depends(require_viewer)) -> dict[str, Any]:
    sources = list(session.scalars(select(SourceModel)).all())
    jobs: list[Callable[[], Any]] = [probe_database, probe_redis_and_notifier, probe_detector, probe_ai,
                                     lambda: probe_streams(sources)]
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        results = list(pool.map(lambda job: job(), jobs))
    components: list[dict[str, Any]] = [component("api", "API", True, "answering", "")]
    for result in results:
        components.extend(result if isinstance(result, list) else [result])
    return {"ok": all(item["ok"] for item in components), "checkedAt": datetime.now(UTC).isoformat(),
            "components": components}
