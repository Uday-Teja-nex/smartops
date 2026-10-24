"""SmartOps worker: consumes candidate-window jobs from Redis.

Per job:
  1. Sample frames from the source within the candidate window (OpenCV).
  2. If a detector is configured, run YOLO detection on the frames, persist
     detections through the API, and gate: windows with nothing detected are
     marked ignored without spending VLM time.
  3. Send surviving candidates (frames + detection context) to the
     orchestrator for LangGraph review.
  4. Persist any returned incident draft through the API.

Failures retry up to SMARTOPS_JOB_MAX_ATTEMPTS then dead-letter.
"""

from __future__ import annotations

import base64
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import httpx
import redis

from app.evidence import generate_and_store_evidence
from app.log import log


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


SOURCE_ROOT = Path(os.getenv("SMARTOPS_SOURCE_ROOT", "/app/sample-data/input"))
API_BASE_URL = os.getenv("SMARTOPS_API_BASE_URL", "http://api:8000").rstrip("/")
ORCHESTRATOR_BASE_URL = os.getenv(
    "SMARTOPS_ORCHESTRATOR_BASE_URL", "http://orchestrator:8100"
).rstrip("/")
# Optional until the detector service ships in compose; empty disables the stage.
DETECTOR_BASE_URL = os.getenv("SMARTOPS_DETECTOR_BASE_URL", "").rstrip("/")
REDIS_URL = os.getenv("SMARTOPS_REDIS_URL", "redis://redis:6379/0")
QUEUE_NAME = os.getenv("SMARTOPS_CANDIDATE_QUEUE", "smartops:candidate_jobs")
DEAD_LETTER_QUEUE = os.getenv("SMARTOPS_DEAD_LETTER_QUEUE", "smartops:candidate_jobs:dead")
SAMPLE_FRAME_COUNT = max(1, env_int("SMARTOPS_SAMPLE_FRAME_COUNT", 3))
MAX_FRAME_WIDTH = max(256, env_int("SMARTOPS_MAX_FRAME_WIDTH", 640))
MAX_ATTEMPTS = max(1, env_int("SMARTOPS_JOB_MAX_ATTEMPTS", 3))
STATUS_TTL_SECONDS = env_int("SMARTOPS_JOB_STATUS_TTL_SECONDS", 24 * 60 * 60)
# Gating heuristics (documented in docs/VIDEO_PIPELINE.md): windows advance to
# VLM review when people cluster or trackable objects appear in walkways.
CROWD_PERSON_THRESHOLD = max(1, env_int("SMARTOPS_CROWD_PERSON_THRESHOLD", 4))
MIN_DETECTION_CONFIDENCE = env_float("SMARTOPS_MIN_DETECTION_CONFIDENCE", 0.35)
INTERNAL_TOKEN = os.getenv("SMARTOPS_INTERNAL_TOKEN", "smartops-internal-dev-token")

OBJECT_HINT_LABELS = {
    "backpack",
    "suitcase",
    "handbag",
    "umbrella",
    "chair",
    "bench",
    "bicycle",
    "potted plant",
    "sports ball",
    "skateboard",
    "bottle",
    "cup",
    "bowl",
    "laptop",
    "tv",
    "box",
}


def source_path_from_uri(source_uri: str) -> Path:
    source_root = SOURCE_ROOT.resolve()
    source_path = Path(source_uri).resolve()
    if source_root not in source_path.parents:
        raise ValueError(f"source path outside allowed root: {source_uri}")
    if not source_path.exists():
        raise FileNotFoundError(source_uri)
    return source_path


def resize_frame(frame: Any) -> Any:
    height, width = frame.shape[:2]
    if width <= MAX_FRAME_WIDTH:
        return frame
    scale = MAX_FRAME_WIDTH / width
    next_size = (MAX_FRAME_WIDTH, max(1, int(height * scale)))
    return cv2.resize(frame, next_size, interpolation=cv2.INTER_AREA)


def sample_frames(
    path: Path,
    window_start: float | None,
    window_end: float | None,
    frame_count_target: int,
) -> list[dict[str, Any]]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"unable to open video: {path.name}")

    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    if total_frames <= 0:
        capture.release()
        raise RuntimeError(f"video has no readable frames: {path.name}")

    if fps > 0 and window_start is not None and window_end is not None:
        first_frame = max(0, int(window_start * fps))
        last_frame = min(total_frames - 1, int(window_end * fps))
    else:
        first_frame, last_frame = 0, total_frames - 1
    if last_frame < first_frame:
        first_frame, last_frame = 0, total_frames - 1

    span = last_frame - first_frame
    if frame_count_target == 1 or span <= 0:
        indexes = [first_frame + span // 2]
    else:
        indexes = [
            first_frame + round(span * index / (frame_count_target - 1))
            for index in range(frame_count_target)
        ]

    samples: list[dict[str, Any]] = []
    for frame_index in indexes:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok:
            continue
        frame = resize_frame(frame)
        encoded_ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not encoded_ok:
            continue
        timestamp = frame_index / fps if fps > 0 else 0
        samples.append(
            {
                "frameIndex": int(frame_index),
                "timestampSeconds": round(timestamp, 2),
                "imageBase64": base64.b64encode(encoded.tobytes()).decode("utf-8"),
            }
        )

    capture.release()
    if not samples:
        raise RuntimeError(f"no frames could be sampled: {path.name}")
    return samples


def set_status(redis_client: redis.Redis, candidate_id: str, status: dict[str, Any]) -> None:
    status["candidateId"] = candidate_id
    status["updatedAt"] = datetime.now(UTC).isoformat()
    redis_client.set(
        f"smartops:candidate_status:{candidate_id}",
        json.dumps(status),
        ex=STATUS_TTL_SECONDS,
    )


def wait_for_dependencies(client: httpx.Client, redis_client: redis.Redis) -> None:
    while True:
        try:
            api = client.get(f"{API_BASE_URL}/health")
            orchestrator = client.get(f"{ORCHESTRATOR_BASE_URL}/health")
            redis_client.ping()
            if api.is_success and orchestrator.is_success:
                return
        except (httpx.HTTPError, redis.RedisError):
            pass
        log("waiting_for_dependencies", api=API_BASE_URL, orchestrator=ORCHESTRATOR_BASE_URL)
        time.sleep(5)


def run_detection(
    client: httpx.Client,
    job: dict[str, Any],
    frames: list[dict[str, Any]],
    min_confidence: float,
) -> dict[str, Any]:
    """Call the detector service. Returns a detection context dict.

    status: "ran" | "disabled" | "unavailable"
    """
    if not DETECTOR_BASE_URL:
        return {"status": "disabled", "detections": []}

    try:
        response = client.post(
            f"{DETECTOR_BASE_URL}/v1/detect",
            json={
                "frames": [
                    {
                        "frameIndex": frame["frameIndex"],
                        "timestampSeconds": frame["timestampSeconds"],
                        "imageBase64": frame["imageBase64"],
                    }
                    for frame in frames
                ],
                "minConfidence": min_confidence,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        payload = response.json()
        return {
            "status": "ran",
            "modelName": payload.get("modelName", "unknown"),
            "backend": payload.get("backend", "unknown"),
            "detections": payload.get("detections", []),
        }
    except httpx.HTTPError as exc:
        log(
            "detector_unavailable",
            level="warning",
            candidateId=job.get("candidateId"),
            error=f"{exc.__class__.__name__}: {exc}",
        )
        return {"status": "unavailable", "detections": [], "error": str(exc)}


def persist_detections(
    client: httpx.Client, job: dict[str, Any], detection_context: dict[str, Any]
) -> list[dict[str, Any]]:
    detections = detection_context.get("detections", [])
    if not detections:
        return []
    source = job.get("source") or job.get("camera") or {}
    body = {
        "detections": [
            {
                "sourceId": source.get("id"),
                "candidateId": job["candidateId"],
                "label": det["label"],
                "confidence": det["confidence"],
                "bbox": det["bbox"],
                "frameTs": det["timestampSeconds"],
                "frameIndex": det["frameIndex"],
                "modelName": detection_context.get("modelName", "unknown"),
            }
            for det in detections
        ]
    }
    response = client.post(f"{API_BASE_URL}/v1/detections", json=body)
    response.raise_for_status()
    return response.json()


def summarize_detections(detections: list[dict[str, Any]]) -> dict[str, Any]:
    label_counts: dict[str, int] = {}
    person_by_frame: dict[int, int] = {}
    for det in detections:
        label = det["label"]
        label_counts[label] = label_counts.get(label, 0) + 1
        if label == "person":
            frame = int(det["frameIndex"])
            person_by_frame[frame] = person_by_frame.get(frame, 0) + 1
    return {
        "labels": label_counts,
        "maxPersonsInFrame": max(person_by_frame.values(), default=0),
        "totalDetections": len(detections),
    }


def should_send_to_orchestrator(detection_context: dict[str, Any]) -> tuple[bool, str]:
    """Worker-side pre-gate to avoid orchestrator calls for empty windows.

    Full review policy lives in the LangGraph orchestrator; this only skips
    windows where the detector ran successfully and saw nothing at all.
    """
    if detection_context["status"] != "ran":
        # No detector or detector down: forward so the graph can route to
        # human review honestly instead of dropping footage silently.
        return True, detection_context["status"]

    summary = summarize_detections(detection_context.get("detections", []))
    if summary["totalDetections"] == 0:
        return False, "no_detections"

    interesting = summary["maxPersonsInFrame"] >= CROWD_PERSON_THRESHOLD or any(
        label in OBJECT_HINT_LABELS for label in summary["labels"]
    )
    if not interesting and summary["labels"].keys() <= {"person"} and summary["maxPersonsInFrame"] < 2:
        return False, "single_person_only"
    return True, "detections_present"


def process_job(client: httpx.Client, redis_client: redis.Redis, job: dict[str, Any]) -> str:
    candidate_id = str(job["candidateId"])
    source = job.get("source") or job.get("camera") or {}
    detection_config = source.get("detectionConfig") or {}
    source_path = source_path_from_uri(str(job["sourceUri"]))

    set_status(
        redis_client,
        candidate_id,
        {
            "state": "processing",
            "sourceId": source.get("id"),
            "sourceName": job.get("sourceName"),
            "attempt": job.get("attempt", 0),
        },
    )

    frames = sample_frames(
        source_path,
        job.get("windowStart"),
        job.get("windowEnd"),
        int(detection_config.get("sampleFramesPerWindow") or SAMPLE_FRAME_COUNT),
    )

    min_confidence = float(detection_config.get("minConfidence") or MIN_DETECTION_CONFIDENCE)
    detection_context = run_detection(client, job, frames, min_confidence)
    persisted = persist_detections(client, job, detection_context)
    detection_summary = summarize_detections(detection_context.get("detections", []))
    detection_summary["detectorStatus"] = detection_context["status"]
    if detection_context.get("modelName"):
        detection_summary["modelName"] = detection_context["modelName"]

    forward, gate_reason = should_send_to_orchestrator(detection_context)
    if not forward:
        set_status(
            redis_client,
            candidate_id,
            {
                "state": "ignored",
                "sourceId": source.get("id"),
                "sourceName": job.get("sourceName"),
                "gate": gate_reason,
                "detections": detection_summary["totalDetections"],
            },
        )
        return f"candidate={candidate_id} gated reason={gate_reason}"

    payload = {
        "candidateId": candidate_id,
        "sourceUri": job["sourceUri"],
        "sourceName": job["sourceName"],
        "observedAt": datetime.now(UTC).isoformat(),
        "windowStart": job.get("windowStart"),
        "windowEnd": job.get("windowEnd"),
        "camera": {
            "id": source.get("id"),
            "buildingId": source.get("buildingId"),
            "floor": source.get("floor"),
            "zone": source.get("zone"),
        },
        "frames": [
            {
                "timestampSeconds": frame["timestampSeconds"],
                "imageBase64": frame["imageBase64"],
            }
            for frame in frames
        ],
        "detectionContext": {
            "status": detection_context["status"],
            "summary": detection_summary,
            "detections": [
                {
                    "label": det["label"],
                    "confidence": det["confidence"],
                    "bbox": det["bbox"],
                    "timestampSeconds": det["timestampSeconds"],
                }
                for det in detection_context.get("detections", [])
            ],
        },
    }

    review = client.post(f"{ORCHESTRATOR_BASE_URL}/v1/candidates/review", json=payload)
    review.raise_for_status()
    result = review.json()
    if not result.get("createIncident"):
        set_status(
            redis_client,
            candidate_id,
            {
                "state": "review_unavailable" if result.get("routeTo") == "human-review" else "ignored",
                "sourceId": source.get("id"),
                "sourceName": job.get("sourceName"),
                "routeTo": result.get("routeTo"),
                "notes": result.get("notes", []),
            },
        )
        return f"candidate={candidate_id} route={result.get('routeTo')}"

    incident_draft = result["incident"]
    incident_draft.setdefault("candidateId", candidate_id)
    incident_draft.setdefault("detectionSummary", detection_summary)

    evidence_overrides = generate_and_store_evidence(
        client, API_BASE_URL, job, frames, source_path
    )
    if evidence_overrides:
        incident_draft["evidence"] = {
            **incident_draft.get("evidence", {}),
            **evidence_overrides,
        }

    incident_response = client.post(f"{API_BASE_URL}/v1/incidents", json=incident_draft)
    incident_response.raise_for_status()
    incident = incident_response.json()
    set_status(
        redis_client,
        candidate_id,
        {
            "state": "persisted",
            "sourceId": source.get("id"),
            "sourceName": job.get("sourceName"),
            "incidentId": incident["id"],
            "eventType": incident["type"],
            "confidence": incident["confidence"],
            "detections": detection_summary["totalDetections"],
        },
    )
    return (
        f"candidate={candidate_id} incident={incident['id']} "
        f"type={incident['type']} confidence={incident['confidence']}"
    )


def handle_failure(redis_client: redis.Redis, job: dict[str, Any], error: Exception) -> str:
    candidate_id = str(job.get("candidateId", "unknown"))
    attempt = int(job.get("attempt", 0)) + 1
    job["attempt"] = attempt
    job["lastError"] = f"{error.__class__.__name__}: {error}"
    set_status(
        redis_client,
        candidate_id,
        {
            "state": "retrying" if attempt < MAX_ATTEMPTS else "dead",
            "sourceName": job.get("sourceName"),
            "attempt": attempt,
            "error": job["lastError"],
        },
    )
    if attempt < MAX_ATTEMPTS:
        redis_client.rpush(QUEUE_NAME, json.dumps(job))
        return f"candidate={candidate_id} retry attempt={attempt}/{MAX_ATTEMPTS} error={error}"

    redis_client.lpush(DEAD_LETTER_QUEUE, json.dumps(job))
    return f"candidate={candidate_id} dead_letter={DEAD_LETTER_QUEUE} attempts={attempt} error={error}"


def main() -> None:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    # Generous timeout: orchestrator VLM review on CPU can take minutes.
    request_timeout = env_float("SMARTOPS_WORKER_HTTP_TIMEOUT_SECONDS", 540.0)
    with httpx.Client(
        timeout=request_timeout, headers={"X-Internal-Token": INTERNAL_TOKEN}
    ) as client:
        wait_for_dependencies(client, redis_client)
        log(
            "ready",
            sourceRoot=str(SOURCE_ROOT),
            api=API_BASE_URL,
            orchestrator=ORCHESTRATOR_BASE_URL,
            detector=DETECTOR_BASE_URL or "disabled",
            queue=QUEUE_NAME,
        )

        while True:
            item = redis_client.brpop(QUEUE_NAME, timeout=10)
            if item is None:
                continue

            _, raw_job = item
            try:
                job = json.loads(raw_job)
                outcome = process_job(client, redis_client, job)
                log("job_processed", outcome=outcome)
            except Exception as exc:  # noqa: BLE001 - workers must report and retry.
                try:
                    failed_job = json.loads(raw_job)
                except json.JSONDecodeError:
                    redis_client.lpush(DEAD_LETTER_QUEUE, raw_job)
                    log("job_dead_letter_invalid_json", level="error", error=str(exc))
                    continue
                log("job_failed", level="warning", outcome=handle_failure(redis_client, failed_job, exc))


if __name__ == "__main__":
    main()
