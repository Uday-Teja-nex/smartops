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


# --- Shared-service metrics for the Monitoring page ------------------------
# Scraped from the detector's and orchestrator's Prometheus /metrics. Those
# services are shared by every workspace, so only latency percentiles and
# outcome percentages are returned, never counts that would reveal other
# workspaces' activity.

MIN_SAMPLES = 5


def histogram_quantile(buckets: list[tuple[float, float]], q: float) -> float | None:
    """Upper bound of the first bucket holding the q-th observation (like PromQL
    without interpolation). `buckets` are cumulative (le, count) pairs."""
    ordered = sorted(buckets)
    total = ordered[-1][1] if ordered else 0
    if total < MIN_SAMPLES:
        return None
    for le, count in ordered:
        if count >= q * total:
            return le
    return None


def parse_metrics(body: str) -> dict[str, dict[str, Any]]:
    from prometheus_client.parser import text_string_to_metric_families

    out: dict[str, dict[str, Any]] = {}
    for family in text_string_to_metric_families(body):
        entry = out.setdefault(family.name, {"buckets": [], "samples": []})
        for sample in family.samples:
            if sample.name.endswith("_bucket"):
                entry["buckets"].append((float(sample.labels["le"]), sample.value))
            elif sample.name.endswith("_total") or sample.name == family.name:
                entry["samples"].append((sample.labels, sample.value))
    return out


def summarize_latency(metrics: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    buckets = metrics.get(name, {}).get("buckets", [])
    return {"p50Seconds": histogram_quantile(buckets, .5), "p95Seconds": histogram_quantile(buckets, .95)}


def outcome_shares(metrics: dict[str, dict[str, Any]], name: str, label: str = "outcome") -> dict[str, float] | None:
    totals: dict[str, float] = {}
    for labels, value in metrics.get(name, {}).get("samples", []):
        key = labels.get(label, "unknown")
        totals[key] = totals.get(key, 0) + value
    count = sum(totals.values())
    if count < MIN_SAMPLES:
        return None
    return {key: round(100 * value / count, 1) for key, value in sorted(totals.items())}


def scrape(url: str) -> dict[str, dict[str, Any]] | str:
    try:
        response = httpx.get(url + "/metrics", timeout=TIMEOUT)
        response.raise_for_status()
        return parse_metrics(response.text)
    except Exception as exc:  # noqa: BLE001
        return f"metrics unavailable ({type(exc).__name__})"


@router.get("/metrics")
def system_metrics(principal: Principal = Depends(require_viewer)) -> dict[str, Any]:
    settings = get_settings()
    with ThreadPoolExecutor(max_workers=2) as pool:
        detector, ai = pool.map(scrape, [settings.detector_base_url, settings.orchestrator_base_url])
    result: dict[str, Any] = {"checkedAt": datetime.now(UTC).isoformat(), "minSamples": MIN_SAMPLES,
                              "scope": "shared services, since each service last started"}
    if isinstance(detector, str):
        result["detector"] = {"error": detector}
    else:
        result["detector"] = {**summarize_latency(detector, "smartops_detector_inference_seconds"),
                              "outcomes": outcome_shares(detector, "smartops_detector_requests")}
    if isinstance(ai, str):
        result["ai"] = {"error": ai}
    else:
        result["ai"] = {**summarize_latency(ai, "smartops_ai_review_seconds"),
                        "outcomes": outcome_shares(ai, "smartops_ai_reviews")}
    return result
