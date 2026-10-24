"""Unit tests for the worker's detection gating and retry logic.

cv2/httpx are imported by app.main; they are in the worker requirements and
are import-safe without a display or network.
"""

import json

import httpx
import pytest

from app.main import (
    handle_failure,
    should_send_to_orchestrator,
    summarize_detections,
)


def _det(label: str, frame: int = 0, confidence: float = 0.8):
    return {
        "label": label,
        "confidence": confidence,
        "frameIndex": frame,
        "timestampSeconds": float(frame),
        "bbox": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2},
    }


class FakeRedis:
    def __init__(self):
        self.lists: dict[str, list[str]] = {}
        self.kv: dict[str, str] = {}

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)

    def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)

    def set(self, key, value, ex=None):
        self.kv[key] = value


@pytest.mark.parametrize("detected,expected", [(False, "ignored"), (True, "review_unavailable")])
def test_no_incident_written_for_gated_or_failed_review(monkeypatch, tmp_path, detected, expected):
    from app import main

    source_path = tmp_path / "sample.mp4"
    source_path.touch()
    monkeypatch.setattr(main, "SOURCE_ROOT", tmp_path)

    monkeypatch.setattr(main, "sample_frames", lambda *args: [])
    monkeypatch.setattr(main, "run_detection", lambda *args: {
        "status": "ran", "detections": [_det("suitcase")] if detected else [],
    })
    monkeypatch.setattr(main, "persist_detections", lambda *args: [])
    requests = []

    def respond(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={
            "createIncident": False, "routeTo": "human-review", "notes": ["VLM unavailable"],
        })

    redis = FakeRedis()
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        main.process_job(client, redis, {
            "candidateId": "cand-failure", "sourceName": "camera", "sourceUri": str(source_path),
            "source": {"id": "src-1"},
        })
    status = json.loads(redis.kv["smartops:candidate_status:cand-failure"])
    assert status["state"] == expected
    assert "/v1/incidents" not in requests
    if detected:
        assert status["notes"] == ["VLM unavailable"]
    else:
        assert requests == []


def test_summarize_detections_counts_people_per_frame():
    summary = summarize_detections(
        [_det("person", 0), _det("person", 0), _det("person", 1), _det("chair", 1)]
    )
    assert summary["labels"] == {"person": 3, "chair": 1}
    assert summary["maxPersonsInFrame"] == 2
    assert summary["totalDetections"] == 4


def test_gate_skips_empty_windows_when_detector_ran():
    forward, reason = should_send_to_orchestrator({"status": "ran", "detections": []})
    assert forward is False
    assert reason == "no_detections"


def test_gate_skips_single_person_only():
    forward, reason = should_send_to_orchestrator(
        {"status": "ran", "detections": [_det("person")]}
    )
    assert forward is False
    assert reason == "single_person_only"


def test_gate_forwards_crowds():
    detections = [_det("person", 0) for _ in range(5)]
    forward, reason = should_send_to_orchestrator({"status": "ran", "detections": detections})
    assert forward is True
    assert reason == "detections_present"


def test_gate_forwards_object_hints():
    forward, _ = should_send_to_orchestrator(
        {"status": "ran", "detections": [_det("suitcase")]}
    )
    assert forward is True


def test_gate_forwards_when_detector_disabled_or_unavailable():
    # The graph decides what to do with these — the worker must not drop
    # footage silently when detection was not possible.
    for status in ("disabled", "unavailable"):
        forward, reason = should_send_to_orchestrator({"status": status, "detections": []})
        assert forward is True
        assert reason == status


def test_handle_failure_retries_then_dead_letters():
    redis = FakeRedis()
    job = {"candidateId": "cand-x", "sourceName": "x.mp4", "attempt": 0}

    outcome = handle_failure(redis, job, RuntimeError("boom"))
    assert "retry attempt=1/3" in outcome

    job["attempt"] = 2  # simulate the final allowed attempt failing
    outcome = handle_failure(redis, job, RuntimeError("boom again"))
    assert "dead_letter" in outcome

    dead = redis.lists.get("smartops:candidate_jobs:dead", [])
    assert len(dead) == 1
    dead_job = json.loads(dead[0])
    assert dead_job["attempt"] == 3
    assert "boom again" in dead_job["lastError"]

    status_key = "smartops:candidate_status:cand-x"
    status = json.loads(redis.kv[status_key])
    assert status["state"] == "dead"
