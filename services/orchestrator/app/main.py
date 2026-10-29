import os
from fastapi import FastAPI, HTTPException
from app.enrichment import EnrichmentRequest, EnrichmentResponse, enrich

from app.graph import REVIEW_CONFIDENCE_THRESHOLD, build_graph, describe_graph
from app.providers.factory import get_model_provider
from app.schemas import CandidateReviewRequest, CandidateReviewResponse, EvidenceDraft, IncidentDraft

app = FastAPI(title="SmartOps Orchestrator", version="0.2.0")
provider = get_model_provider()
graph = build_graph(provider)


@app.post('/v1/incidents/enrich', response_model=EnrichmentResponse)
def enrich_incident(payload: EnrichmentRequest):
    try:
        return enrich(provider, payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail='AI enrichment unavailable: ' + type(exc).__name__) from None


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
