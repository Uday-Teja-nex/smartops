"""Graph routing tests with a canned provider (no Ollama required)."""

from pathlib import Path
from typing import Any

from app.catalog import EVENT_CATALOG, VLM_REVIEWABLE_TYPES
from app.graph import build_graph
from app.providers.base import ModelProvider


class FakeProvider(ModelProvider):
    """Scriptable provider: returns queued responses or raises."""

    vision_model = "fake-vlm"
    text_model = "fake-llm"

    def __init__(self, vlm_response: Any = None, llm_response: Any = None, vlm_raises: bool = False):
        self.vlm_response = vlm_response
        self.llm_response = llm_response or {
            "detailed_narrative": ["n1", "n2"],
            "recommended_actions": ["a1", "a2"],
        }
        self.vlm_raises = vlm_raises
        self.vlm_calls = 0

    def review_event_evidence(self, prompt, image_paths: list[Path], schema=None):
        raise NotImplementedError

    def review_event_evidence_base64(self, prompt, images, schema=None):
        self.vlm_calls += 1
        if self.vlm_raises:
            raise RuntimeError("model exploded")
        return self.vlm_response

    def summarize_incident(self, prompt, schema=None):
        return self.llm_response

    def suggest_actions(self, prompt, schema=None):
        return self.llm_response


def _base_state(**overrides):
    state = {
        "candidate_id": "cand-1",
        "source_uri": "/x.mp4",
        "source_name": "x.mp4",
        "observed_at": "2026-07-07T10:00:00+00:00",
        "camera": {"id": "src-1", "buildingId": "b-1", "floor": "L1", "zone": "Lobby"},
        "frame_images": ["aGVsbG8="],
        "frame_timestamps": [1.0],
        "detection_context": {
            "status": "ran",
            "summary": {"labels": {"person": 4}, "maxPersonsInFrame": 4},
            "detections": [
                {"label": "person", "confidence": 0.8, "bbox": {}, "timestampSeconds": 1.0}
            ],
        },
        "model_provider": "fake",
        "model_version": "fake-vlm/fake-llm",
    }
    state.update(overrides)
    return state


def test_confident_review_creates_active_incident():
    provider = FakeProvider(
        vlm_response={
            "event_detected": True,
            "event_type": "exit_blocked",
            "severity": "critical",
            "confidence": 0.92,
            "short_summary": "Exit blocked",
            "observations": ["obs1"],
        }
    )
    graph = build_graph(provider)
    state = graph.invoke(_base_state())

    incident = state["incident"]
    assert incident["status"] == "active"
    assert incident["category"] == "Safety"
    assert incident["subcategory"] == "blocked_exit"
    assert incident["confidence"] == 0.92
    assert incident["slaDueAt"] is not None
    assert incident["sourceId"] == "src-1"
    assert state["route_to"] == "operations"


def test_low_confidence_routes_to_human_review():
    provider = FakeProvider(
        vlm_response={
            "event_detected": True,
            "event_type": "bin_overflow",
            "severity": "medium",
            "confidence": 0.4,
            "short_summary": "Maybe a bin",
            "observations": [],
        }
    )
    graph = build_graph(provider)
    state = graph.invoke(_base_state())
    assert state["route_to"] == "human-review"
    assert state["incident"]["status"] == "human_review"
    assert any("below threshold" in note for note in state["incident"]["reviewNotes"])


def test_invalid_model_output_falls_back_to_human_review():
    provider = FakeProvider(vlm_response={"garbage": True})
    graph = build_graph(provider)
    state = graph.invoke(_base_state())
    assert state["route_to"] == "human-review"
    assert state["incident"]["status"] == "human_review"


def test_model_exception_falls_back_to_human_review():
    provider = FakeProvider(vlm_raises=True)
    graph = build_graph(provider)
    state = graph.invoke(_base_state())
    assert state["route_to"] == "human-review"
    assert any("VLM review failed" in note for note in state["notes"])


def test_no_event_is_ignored():
    provider = FakeProvider(
        vlm_response={
            "event_detected": False,
            "event_type": "no_event",
            "confidence": 0.9,
        }
    )
    graph = build_graph(provider)
    state = graph.invoke(_base_state())
    assert state["route_to"] == "ignored"
    assert "incident" not in state


def test_unsupported_event_type_is_ignored():
    provider = FakeProvider(
        vlm_response={
            "event_detected": True,
            "event_type": "alien_invasion",
            "confidence": 0.99,
        }
    )
    graph = build_graph(provider)
    state = graph.invoke(_base_state())
    assert state["route_to"] == "ignored"


def test_detector_unavailable_skips_vlm_and_routes_human_review():
    provider = FakeProvider(vlm_response={"event_detected": False, "event_type": "no_event", "confidence": 0})
    graph = build_graph(provider)
    state = graph.invoke(
        _base_state(detection_context={"status": "unavailable", "detections": []})
    )
    assert provider.vlm_calls == 0
    assert state["route_to"] == "human-review"
    assert state["incident"]["status"] == "human_review"


def test_empty_detections_after_detector_ran_is_ignored_without_vlm():
    provider = FakeProvider(vlm_response={"event_detected": True, "event_type": "crowding", "confidence": 0.9})
    graph = build_graph(provider)
    state = graph.invoke(
        _base_state(detection_context={"status": "ran", "detections": [], "summary": {}})
    )
    assert provider.vlm_calls == 0
    assert state["route_to"] == "ignored"


def test_no_frames_routes_to_human_review():
    provider = FakeProvider(vlm_response={})
    graph = build_graph(provider)
    state = graph.invoke(_base_state(frame_images=[]))
    assert provider.vlm_calls == 0
    assert state["route_to"] == "human-review"


def test_no_provider_routes_to_human_review():
    graph = build_graph(None)
    state = graph.invoke(_base_state())
    assert state["route_to"] == "human-review"


def test_taxonomy_covers_all_six_categories():
    categories = {entry["category"] for entry in EVENT_CATALOG.values()}
    assert categories == {
        "Safety",
        "Housekeeping",
        "Occupancy",
        "Security",
        "Queue & Crowd",
        "System Health",
    }
    # System Health types are rule-based only, never offered to the VLM.
    for event_type in VLM_REVIEWABLE_TYPES:
        assert EVENT_CATALOG[event_type]["category"] != "System Health"
