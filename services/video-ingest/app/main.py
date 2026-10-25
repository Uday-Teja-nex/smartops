"""SmartOps video ingestion service.

Loop:
  1. (optional) autodiscover MP4 files in SOURCE_ROOT and register them as
     sources via the API (tagged "autodiscovered").
  2. Fetch registered sources from the API.
  3. For each enabled, non-paused source: pick the adapter for its type,
     probe health, report it, and enqueue candidate windows to Redis.

Unsupported source types (RTSP/ONVIF/WebRTC until their adapters land) are
probed honestly: they report an explicit "adapter not implemented" health
state and never fake ingestion.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import redis

from app.adapters import AdapterNotImplemented, get_adapter
from app.log import log


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


SOURCE_ROOT = Path(os.getenv("SMARTOPS_SOURCE_ROOT", "/app/sample-data/input"))
API_BASE_URL = os.getenv("SMARTOPS_API_BASE_URL", "http://api:8000").rstrip("/")
REDIS_URL = os.getenv("SMARTOPS_REDIS_URL", "redis://redis:6379/0")
QUEUE_NAME = os.getenv("SMARTOPS_CANDIDATE_QUEUE", "smartops:candidate_jobs")
SCAN_INTERVAL_SECONDS = env_int("SMARTOPS_SCAN_INTERVAL_SECONDS", 30)
JOB_DEDUPE_TTL_SECONDS = env_int("SMARTOPS_JOB_DEDUPE_TTL_SECONDS", 24 * 60 * 60)
AUTODISCOVER_MP4 = os.getenv("SMARTOPS_AUTODISCOVER_MP4", "true").lower() in {"1", "true", "yes"}
DEFAULT_BUILDING_ID = os.getenv("SMARTOPS_DEFAULT_BUILDING_ID", "bldg-north-01")
DEFAULT_FLOOR = os.getenv("SMARTOPS_DEFAULT_FLOOR", "L1")
DEFAULT_ZONE = os.getenv("SMARTOPS_DEFAULT_ZONE", "Lobby Atrium")
INTERNAL_TOKEN = os.getenv("SMARTOPS_INTERNAL_TOKEN", "smartops-internal-dev-token")

SUPPORTED_EXTENSIONS = {".mp4"}


def wait_for_dependencies(client: httpx.Client, redis_client: redis.Redis) -> None:
    while True:
        try:
            api = client.get(f"{API_BASE_URL}/health")
            redis_client.ping()
            if api.is_success:
                return
        except (httpx.HTTPError, redis.RedisError):
            pass
        log("waiting_for_dependencies", api=API_BASE_URL, redis=REDIS_URL)
        time.sleep(5)


def fetch_sources(client: httpx.Client) -> list[dict[str, Any]]:
    response = client.get(f"{API_BASE_URL}/v1/sources")
    response.raise_for_status()
    return response.json()


def autodiscover_mp4_sources(client: httpx.Client, sources: list[dict[str, Any]]) -> int:
    """Register MP4 files found in SOURCE_ROOT that no source points at yet."""
    known_uris = {source.get("sourceUri") for source in sources}
    registered = 0
    for path in sorted(SOURCE_ROOT.glob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        uri = str(path).replace("\\", "/")
        if uri in known_uris:
            continue
        payload = {
            "name": path.stem,
            "buildingId": DEFAULT_BUILDING_ID,
            "floor": DEFAULT_FLOOR,
            "zone": DEFAULT_ZONE,
            "sourceType": "file",
            "sourceUri": uri,
            "inputFormat": "mp4",
            "enabled": True,
            "tags": ["autodiscovered"],
            "positionNotes": "Auto-registered from sample-data/input by video-ingest.",
            "detectionConfig": {},
        }
        response = client.post(f"{API_BASE_URL}/v1/sources", json=payload)
        if response.is_success:
            registered += 1
            log("source_autodiscovered", file=path.name, sourceId=response.json().get("id"))
        else:
            log(
                "source_autodiscover_failed",
                level="warning",
                file=path.name,
                statusCode=response.status_code,
                body=response.text[:200],
            )
    return registered


def report_health(client: httpx.Client, source: dict[str, Any], health: Any) -> None:
    payload = {
        "status": health.status,
        "lastError": health.error,
        "latencyMs": health.latency_ms,
        "adapter": health.adapter,
        "details": health.details,
    }
    response = client.post(f"{API_BASE_URL}/v1/sources/{source['id']}/health", json=payload)
    if not response.is_success:
        log(
            "health_report_failed",
            level="warning",
            sourceId=source["id"],
            statusCode=response.status_code,
        )


def enqueue_window(
    redis_client: redis.Redis,
    source: dict[str, Any],
    window: Any,
) -> str:
    candidate_id = f"{source['id']}-{window.signature}"
    dedupe_key = f"smartops:candidate_dedupe:{candidate_id}"
    status_key = f"smartops:candidate_status:{candidate_id}"

    reserved = redis_client.set(dedupe_key, "queued", nx=True, ex=JOB_DEDUPE_TTL_SECONDS)
    if not reserved:
        return "duplicate"

    queued_at = datetime.now(UTC).isoformat()
    job = {
        "candidateId": candidate_id,
        "sourceUri": source["sourceUri"],
        "sourceName": source["name"],
        "windowIndex": window.window_index,
        "windowStart": window.start_seconds,
        "windowEnd": window.end_seconds,
        "signature": window.signature,
        "queuedAt": queued_at,
        "attempt": 0,
        "source": {
            "id": source["id"],
            "buildingId": source["buildingId"],
            "floor": source["floor"],
            "zone": source["zone"],
            "detectionConfig": source.get("detectionConfig") or {},
        },
        # Legacy key kept while the worker/orchestrator migrate.
        "camera": {
            "id": source["id"],
            "buildingId": source["buildingId"],
            "floor": source["floor"],
            "zone": source["zone"],
        },
    }
    redis_client.set(
        status_key,
        json.dumps(
            {
                "state": "queued",
                "candidateId": candidate_id,
                "sourceId": source["id"],
                "sourceName": source["name"],
                "windowStart": window.start_seconds,
                "windowEnd": window.end_seconds,
                "updatedAt": queued_at,
            }
        ),
        ex=JOB_DEDUPE_TTL_SECONDS,
    )
    redis_client.lpush(QUEUE_NAME, json.dumps(job))
    return "queued"


def process_source(
    client: httpx.Client, redis_client: redis.Redis, source: dict[str, Any]
) -> None:
    try:
        adapter = get_adapter(source)
    except AdapterNotImplemented as exc:
        log("adapter_missing", level="warning", sourceId=source["id"], error=str(exc))
        return

    health = adapter.probe()
    health.adapter = adapter.adapter_name
    report_health(client, source, health)

    if not health.ok:
        log(
            "source_unhealthy",
            level="warning",
            sourceId=source["id"],
            adapter=adapter.adapter_name,
            status=health.status,
            error=health.error,
        )
        return

    try:
        windows = adapter.discover_candidates()
    except AdapterNotImplemented as exc:
        log("adapter_pending", level="warning", sourceId=source["id"], error=str(exc))
        return

    queued = 0
    duplicates = 0
    for window in windows:
        outcome = enqueue_window(redis_client, source, window)
        if outcome == "queued":
            queued += 1
        else:
            duplicates += 1
    log(
        "source_scanned",
        sourceId=source["id"],
        adapter=adapter.adapter_name,
        windows=len(windows),
        queued=queued,
        duplicates=duplicates,
    )


def main() -> None:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    with httpx.Client(timeout=30.0, headers={"X-Internal-Token": INTERNAL_TOKEN}) as client:
        wait_for_dependencies(client, redis_client)
        log(
            "ready",
            sourceRoot=str(SOURCE_ROOT),
            api=API_BASE_URL,
            queue=QUEUE_NAME,
            autodiscover=AUTODISCOVER_MP4,
        )

        while True:
            try:
                sources = fetch_sources(client)
                if AUTODISCOVER_MP4:
                    if autodiscover_mp4_sources(client, sources) > 0:
                        sources = fetch_sources(client)

                active = [
                    source
                    for source in sources
                    if source.get("enabled") and source.get("status") != "paused"
                    and source.get("sourceType") != "rtsp"
                ]
                log("scan_start", total=len(sources), active=len(active))
                for source in active:
                    try:
                        process_source(client, redis_client, source)
                    except Exception as exc:  # noqa: BLE001 - keep the loop alive per source.
                        log(
                            "source_scan_failed",
                            level="error",
                            sourceId=source.get("id"),
                            error=f"{exc.__class__.__name__}: {exc}",
                        )
            except Exception as exc:  # noqa: BLE001 - retry on next interval.
                log("scan_failed", level="error", error=f"{exc.__class__.__name__}: {exc}")

            time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
