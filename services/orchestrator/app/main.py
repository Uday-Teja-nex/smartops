import logging
import os
from fastapi import FastAPI, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from app.enrichment import EnrichmentRequest, EnrichmentResponse, describe_failure, enrich

from app.graph import REVIEW_CONFIDENCE_THRESHOLD, build_graph, describe_graph
from app.providers.factory import get_model_provider
from app.schemas import CandidateReviewRequest, CandidateReviewResponse, EvidenceDraft, IncidentDraft

app = FastAPI(title="SmartOps Orchestrator", version="0.2.0")
provider = get_model_provider()
graph = build_graph(provider)


# Outcome of the most recent real review, for status pages (in-process only).
last_review: dict = {}
REVIEWS = Counter("smartops_ai_reviews_total", "AI review outcomes", ["outcome", "reason"])
REVIEW_SECONDS = Histogram("smartops_ai_review_seconds", "AI review time including queue wait",
                           buckets=(1, 2, 5, 10, 20, 30, 60, 120))


def _reason_label(reason: str) -> str:
    for key in ("daily request limit", "rate limit", "API key", "did not answer", "unreachable", "validation",
                "loading", "busy", "provider error", "refused", "not found"):
        if key in reason:
            return key.replace(" ", "_")
    return "other"


@app.post('/v1/incidents/enrich', response_model=EnrichmentResponse)
def enrich_incident(payload: EnrichmentRequest):
    import time
    try:
        result = enrich(provider, payload)
        REVIEWS.labels("validated", "").inc()
        REVIEW_SECONDS.observe(result.latencyMs / 1000)
        last_review.clear()
        last_review.update(ok=True, at=time.time(), model=result.model, latencyMs=result.latencyMs)
        return result
    except Exception as exc:
        reason = describe_failure(exc)
        REVIEWS.labels("unavailable", _reason_label(reason)).inc()
        last_review.clear()
        last_review.update(ok=False, at=time.time(), reason=reason)
        logging.getLogger('smartops.enrichment').warning(
            'enrichment failed incident=%s reason=%s error=%s', payload.incidentId, reason, type(exc).__name__)
        raise HTTPException(status_code=503, detail=reason) from None


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/v1/status")
def status() -> dict:
    """AI review availability: provider check plus the last real outcome."""
    import time
    check = provider.availability() if hasattr(provider, 'availability') else {'ok': True, 'detail': 'unknown'}
    recent = dict(last_review)
    if recent:
        recent['secondsAgo'] = round(time.time() - recent.pop('at'))
    ok = bool(check.get('ok')) and not (recent and not recent.get('ok') and recent['secondsAgo'] < 300)
    return {'ok': ok, 'provider': os.getenv('SMARTOPS_MODEL_PROVIDER', 'ollama'),
            'model': check.get('model'), 'detail': check.get('detail'), 'lastReview': recent or None}


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "orchestrator",
        "engine": "langgraph",
    }


@app.get("/v1/graph")
def graph_shape() -> dict[str, object]:
    return {
        "engine": "langgraph",
        "compiled": graph is not None,
        "provider": provider.__class__.__name__,
        "confidenceThreshold": REVIEW_CONFIDENCE_THRESHOLD,
        **describe_graph(),
    }


@app.post("/v1/candidates/review", response_model=CandidateReviewResponse)
def review_candidate(payload: CandidateReviewRequest) -> CandidateReviewResponse:
    state = graph.invoke(
        {
            "candidate_id": payload.candidateId,
            "source_uri": payload.sourceUri,
            "source_name": payload.sourceName,
            "observed_at": payload.observedAt.isoformat(),
            "window_start": payload.windowStart,
            "window_end": payload.windowEnd,
            "camera": payload.camera.model_dump(),
            "frame_images": [frame.imageBase64 for frame in payload.frames],
            "frame_timestamps": [frame.timestampSeconds for frame in payload.frames],
            "detection_context": payload.detectionContext.model_dump(),
            "model_provider": os.getenv('SMARTOPS_MODEL_PROVIDER', 'ollama'),
            "model_version": f"{provider.vision_model}/{provider.text_model}",
        }
    )

    incident = state.get("incident")
    return CandidateReviewResponse(
        candidateId=payload.candidateId,
        createIncident=incident is not None,
        routeTo=state.get("route_to", "human-review"),
        incident=IncidentDraft(
            **{
                **incident,
                "evidence": EvidenceDraft(**incident["evidence"]),
            }
        )
        if incident
        else None,
        notes=state.get("notes", []),
    )
