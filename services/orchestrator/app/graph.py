"""LangGraph incident-review pipeline.

Shape:

    ingest_candidate
        -> gather_evidence
        -> should_review (conditional)
             -> run_vlm_review -> run_llm_summary -> apply_policy -> END
             -> human_review_fallback -> apply_policy -> END
             -> ignore -> END

Every model response is validated with Pydantic. Anything unparseable or
below the confidence threshold is routed to human review — the system never
fabricates a confident detection.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field, ValidationError

from app.catalog import EVENT_CATALOG, VLM_REVIEWABLE_TYPES
from app.providers.base import ModelProvider

REVIEW_CONFIDENCE_THRESHOLD = float(os.getenv("SMARTOPS_REVIEW_CONFIDENCE_THRESHOLD", "0.6"))


class VlmReview(BaseModel):
    """Validated shape of the VLM scene review."""

    event_detected: bool
    event_type: str
    severity: Literal["low", "medium", "high", "critical"] | None = None
    confidence: float = Field(ge=0, le=1)
    short_summary: str = ""
    observations: list[str] = Field(default_factory=list)


VLM_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "event_detected": {"type": "boolean"},
        "event_type": {"type": "string", "enum": [*VLM_REVIEWABLE_TYPES, "no_event"]},
        "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "short_summary": {"type": "string"},
        "observations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["event_detected", "event_type", "confidence"],
}


class LlmSummary(BaseModel):
    detailed_narrative: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


LLM_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "detailed_narrative": {"type": "array", "items": {"type": "string"}},
        "recommended_actions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["detailed_narrative", "recommended_actions"],
}


class IncidentGraphState(TypedDict, total=False):
    candidate_id: str
    source_uri: str
    source_name: str
    observed_at: str
    window_start: float | None
    window_end: float | None
    camera: dict[str, Any]
    frame_images: list[str]
    frame_timestamps: list[float]
    detection_context: dict[str, Any]
    event_detected: bool
    event_type: str
    severity: str
    confidence: float
    summary: str
    observations: list[str]
    recommended_actions: list[str]
    route_to: str
    review_status: str  # incident status to persist: active | human_review
    model_provider: str
    model_version: str
    notes: list[str]
    incident: dict[str, Any]


def _normalize_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number > 1:
        number = number / 100
    return max(0.0, min(number, 1.0))


def _mark_human_review(state: IncidentGraphState, reason: str) -> IncidentGraphState:
    notes = state.setdefault("notes", [])
    notes.append(reason)
    state["event_detected"] = True
    state["event_type"] = state.get("event_type") or "fallen_object"
    state["severity"] = state.get("severity") or "medium"
    state["confidence"] = min(_normalize_confidence(state.get("confidence")), 0.35) or 0.35
    state["summary"] = state.get("summary") or "Video review candidate pending human confirmation"
    state["observations"] = state.get("observations") or [
        "Frames were sampled from the configured source window.",
        "Automated review did not produce a validated result.",
        "This candidate is intentionally routed for human review.",
    ]
    state["recommended_actions"] = state.get("recommended_actions") or [
        "Open the evidence and confirm whether an operational issue exists.",
        "Tune prompts, models, or sampling if this repeats.",
        "Do not treat this as a confirmed incident until reviewed.",
    ]
    state["route_to"] = "human-review"
    state["review_status"] = "human_review"
    return state


def ingest_candidate(state: IncidentGraphState) -> IncidentGraphState:
    state.setdefault("notes", [])
    state.setdefault("frame_images", [])
    state.setdefault("frame_timestamps", [])
    state.setdefault("detection_context", {"status": "disabled", "detections": []})
    state.setdefault("review_status", "active")
    return state


def gather_evidence(state: IncidentGraphState) -> IncidentGraphState:
    if not state.get("frame_images"):
        return _mark_human_review(state, "No sampled frames were provided by the worker.")
    return state


def decide_review_route(state: IncidentGraphState) -> str:
    """Conditional edge: choose VLM review, honest fallback, or ignore."""
    if state.get("route_to") == "human-review":
        return "human_review_fallback"

    context = state.get("detection_context") or {}
    status = context.get("status", "disabled")
    if status == "unavailable":
        state.setdefault("notes", []).append(
            "Detector service was unavailable; candidate requires human review."
        )
        return "human_review_fallback"
    if status == "ran" and not context.get("detections"):
        # Worker normally gates these; double-check here so the VLM is never
        # spent on empty windows.
        state.setdefault("notes", []).append("Detector found nothing in this window.")
        return "ignore"
    return "run_vlm_review"


def human_review_fallback(state: IncidentGraphState) -> IncidentGraphState:
    if state.get("route_to") != "human-review":
        _mark_human_review(state, "Routed to human review by policy.")
    return state


def ignore_candidate(state: IncidentGraphState) -> IncidentGraphState:
    state["event_detected"] = False
    state["route_to"] = "ignored"
    return state


def _detection_prompt_block(context: dict[str, Any]) -> str:
    detections = context.get("detections") or []
    if not detections:
        return "No object detections are available for these frames."
    lines = ["YOLO object detections for these frames (label, confidence, time):"]
    for det in detections[:25]:
        lines.append(
            f"- {det.get('label')} ({float(det.get('confidence', 0)):.2f}) at {det.get('timestampSeconds')}s"
        )
    summary = context.get("summary") or {}
    if summary.get("maxPersonsInFrame"):
        lines.append(f"Max people in one frame: {summary['maxPersonsInFrame']}")
    return "\n".join(lines)


def run_vlm_review(provider: ModelProvider | None):
    def node(state: IncidentGraphState) -> IncidentGraphState:
        if provider is None:
            return _mark_human_review(state, "No model provider is configured.")

        allowed_types = ", ".join(VLM_REVIEWABLE_TYPES)
        camera = state.get("camera", {})
        prompt = f"""
You are reviewing privacy-safe CCTV evidence for building operations.
Classify only scene-level operational events. Do not identify people.

Allowed event_type values: {allowed_types}
If nothing operationally relevant is visible, set event_detected=false and event_type="no_event".

{_detection_prompt_block(state.get("detection_context") or {})}

Source: {state.get("source_name")}
Camera zone: {camera.get("floor")} {camera.get("zone")}
Return JSON only.
"""
        try:
            raw = provider.review_event_evidence_base64(
                prompt=prompt,
                images=state.get("frame_images", []),
                schema=VLM_RESPONSE_SCHEMA,
            )
        except Exception as exc:  # noqa: BLE001 - local inference failures are non-fatal.
            return _mark_human_review(state, f"VLM review failed: {exc.__class__.__name__}.")

        try:
            review = VlmReview.model_validate(raw)
        except ValidationError:
            return _mark_human_review(state, "VLM returned an invalid or unparseable structure.")

        if not review.event_detected or review.event_type not in EVENT_CATALOG:
            state["event_detected"] = False
            state["route_to"] = "ignored"
            state.setdefault("notes", []).append(
                "VLM did not detect a supported operational event."
            )
            return state

        catalog = EVENT_CATALOG[review.event_type]
        state["event_detected"] = True
        state["event_type"] = review.event_type
        state["severity"] = review.severity or catalog["severity"]
        state["confidence"] = _normalize_confidence(review.confidence)
        state["summary"] = review.short_summary or catalog["summary"]
        state["observations"] = [str(item) for item in review.observations[:4]]
        state["route_to"] = "operations"
        return state

    return node


def run_llm_summary(provider: ModelProvider | None):
    def node(state: IncidentGraphState) -> IncidentGraphState:
        if not state.get("event_detected") or state.get("route_to") == "human-review":
            return state

        event_type = state.get("event_type", "fallen_object")
        catalog = EVENT_CATALOG.get(event_type, EVENT_CATALOG["fallen_object"])
        if provider is None:
            state["recommended_actions"] = list(catalog["actions"])
            return state

        prompt = json.dumps(
            {
                "task": "Create concise operator workflow copy for a smart-building incident.",
                "event_type": event_type,
                "severity": state.get("severity"),
                "summary": state.get("summary"),
                "observations": state.get("observations", []),
            }
        )
        try:
            raw = provider.summarize_incident(prompt, schema=LLM_RESPONSE_SCHEMA)
            summary = LlmSummary.model_validate(raw)
        except Exception as exc:  # noqa: BLE001 - includes ValidationError.
            state.setdefault("notes", []).append(
                f"LLM summary failed: {exc.__class__.__name__}; using catalog actions."
            )
            state["recommended_actions"] = list(catalog["actions"])
            return state

        if summary.detailed_narrative:
            state["observations"] = [str(item) for item in summary.detailed_narrative[:4]]
        state["recommended_actions"] = (
            [str(item) for item in summary.recommended_actions[:4]]
            if summary.recommended_actions
            else list(catalog["actions"])
        )
        return state

    return node


def apply_policy(state: IncidentGraphState) -> IncidentGraphState:
    if not state.get("event_detected"):
        state["route_to"] = "ignored"
        return state

    event_type = state.get("event_type", "fallen_object")
    catalog = EVENT_CATALOG.get(event_type, EVENT_CATALOG["fallen_object"])
    confidence = _normalize_confidence(state.get("confidence"))

    # Low-confidence results are persisted as human_review, not silently
    # published as confirmed incidents.
    if state.get("route_to") != "human-review" and confidence < REVIEW_CONFIDENCE_THRESHOLD:
        state.setdefault("notes", []).append(
            f"Confidence {confidence:.2f} is below threshold {REVIEW_CONFIDENCE_THRESHOLD:.2f}."
        )
        state["route_to"] = "human-review"
        state["review_status"] = "human_review"

    camera = state.get("camera", {})
    observed_at = state.get("observed_at") or datetime.now(UTC).isoformat()
    try:
        start_dt = datetime.fromisoformat(observed_at)
    except ValueError:
        start_dt = datetime.now(UTC)
    sla_due = (start_dt + timedelta(minutes=catalog["sla_minutes"])).isoformat()

    detection_context = state.get("detection_context") or {}
    state["incident"] = {
        "id": f"inc-{state.get('candidate_id')}",
        "category": catalog["category"],
        "subcategory": catalog["subcategory"],
        "type": event_type,
        "severity": state.get("severity") or catalog["severity"],
        "confidence": confidence,
        "status": state.get("review_status", "active"),
        "buildingId": camera.get("buildingId"),
        "floor": camera.get("floor"),
        "zone": camera.get("zone"),
        "sourceId": camera.get("id"),
        "cameraId": camera.get("id"),
        "candidateId": state.get("candidate_id"),
        "startTime": observed_at,
        "endTime": None,
        "slaDueAt": sla_due,
        "shortSummary": state.get("summary") or catalog["summary"],
        "detailedNarrative": state.get("observations")
        or [
            "Candidate was generated from sampled video evidence.",
            "No identity matching or biometric recognition was used.",
            "Human review remains part of the operational workflow.",
        ],
        "recommendedActions": state.get("recommended_actions") or catalog["actions"],
        "reviewNotes": state.get("notes", []),
        "evidence": {
            "thumbnailUrl": "/evidence-placeholder.svg",
            "clipUrl": "/restricted",
            "restricted": True,
        },
        "assignedTo": None,
        "modelProvider": state.get("model_provider", "ollama"),
        "modelVersion": state.get("model_version", "unknown"),
        "detectionSummary": detection_context.get("summary") or {},
    }
    return state


def build_graph(provider: ModelProvider | None = None):
    graph = StateGraph(IncidentGraphState)
    graph.add_node("ingest_candidate", ingest_candidate)
    graph.add_node("gather_evidence", gather_evidence)
    graph.add_node("run_vlm_review", run_vlm_review(provider))
    graph.add_node("human_review_fallback", human_review_fallback)
    graph.add_node("ignore", ignore_candidate)
    graph.add_node("run_llm_summary", run_llm_summary(provider))
    graph.add_node("apply_policy", apply_policy)

    graph.set_entry_point("ingest_candidate")
    graph.add_edge("ingest_candidate", "gather_evidence")
    graph.add_conditional_edges(
        "gather_evidence",
        decide_review_route,
        {
            "run_vlm_review": "run_vlm_review",
            "human_review_fallback": "human_review_fallback",
            "ignore": "ignore",
        },
    )
    graph.add_edge("run_vlm_review", "run_llm_summary")
    graph.add_edge("human_review_fallback", "apply_policy")
    graph.add_edge("run_llm_summary", "apply_policy")
    graph.add_edge("ignore", END)
    graph.add_edge("apply_policy", END)
    return graph.compile()


def describe_graph() -> dict[str, list[str]]:
    return {
        "nodes": [
            "ingest_candidate",
            "gather_evidence",
            "should_review (conditional)",
            "run_vlm_review",
            "human_review_fallback",
            "ignore",
            "run_llm_summary",
            "apply_policy",
        ],
        "edges": [
            "ingest_candidate -> gather_evidence",
            "gather_evidence -> should_review",
            "should_review -> run_vlm_review | human_review_fallback | ignore",
            "run_vlm_review -> run_llm_summary",
            "human_review_fallback -> apply_policy",
            "run_llm_summary -> apply_policy",
            "ignore -> END",
            "apply_policy -> END",
        ],
    }
