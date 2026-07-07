# SmartOps AI Pipeline

Model flow, validation, fallbacks, and the upgrade path.

## Stages

```
frames (worker) ──▶ YOLO detector ──▶ gate ──▶ LangGraph orchestrator ──▶ incident draft
                    yolov8n CPU              │
                                             ├─ VLM classify (qwen2.5vl:3b, structured JSON)
                                             ├─ LLM summarize (llama3.2:3b, structured JSON)
                                             └─ policy: confidence threshold, SLA, routing
```

## 1. YOLO detection (`services/detector/`)

- `POST /v1/detect`: base64 frames → labels + normalized bboxes + confidence.
- Backend registry (`app/backends/`): `ultralytics-cpu` implemented;
  `onnxruntime`, `openvino`, `cuda`, `remote` are named-but-unimplemented —
  selecting one raises a clear error instead of pretending.
- Weights (`yolov8n.pt`) are baked into the image at build time.
- COCO label → operational hint mapping happens in the worker gate
  (people count → crowd/queue signals; bags/chairs/etc. → object-in-walkway).
  These are documented heuristics, not learned policy.

## 2. LangGraph orchestration (`services/orchestrator/app/graph.py`)

```
ingest_candidate → gather_evidence → should_review ─┬─▶ run_vlm_review → run_llm_summary ─▶ apply_policy → END
                                                    ├─▶ human_review_fallback ───────────▶ apply_policy → END
                                                    └─▶ ignore → END
```

`should_review` routing:
- no frames → human review
- detector `unavailable` → human review (never silently drop footage)
- detector ran but zero detections → ignore (no VLM spend)
- otherwise → VLM review

### Structured outputs & validation

Both model calls pass a JSON schema via Ollama's `format` parameter, and
every response is re-validated with Pydantic (`VlmReview`, `LlmSummary`).
Any exception, timeout, missing field, or out-of-enum event type routes the
candidate to human review with the reason recorded in `notes` →
`incident.reviewNotes`. **The system never fabricates a confident
classification.**

### Taxonomy (`app/catalog.py`)

| Category | Event types |
|---|---|
| Safety | exit_blocked, fire_equipment_obstructed, slip_trip_hazard, wet_floor_no_sign, fallen_object |
| Housekeeping | restroom_service_needed, bin_overflow, litter_hotspot, cleaning_missed |
| Occupancy | floor_occupancy_spike, crowding |
| Security | restricted_zone_entry, tailgating_candidate |
| Queue & Crowd | queue_buildup, lobby_congestion, elevator_queue |
| System Health | camera_offline, feed_degraded (rule-based only — never VLM) |

Each entry defines default severity, SLA minutes, operator summary, and
actions used when the model omits them.

### Policy

- `SMARTOPS_REVIEW_CONFIDENCE_THRESHOLD` (default 0.6): below it, the
  incident persists with `status: human_review`.
- SLA due time = observation time + catalog SLA minutes.
- Incident drafts carry full provenance: `modelProvider`, `modelVersion`
  (`<vision>/<text>`), `detectionSummary`, `candidateId`, `reviewNotes`.

## 3. Provider abstraction (`orchestrator/app/providers/`)

```python
class ModelProvider(ABC):
    def review_event_evidence(...)          # path-based images
    def review_event_evidence_base64(...)   # inter-service frames
    def summarize_incident(...)
    def suggest_actions(...)
```

`factory.get_model_provider()` selects by `SMARTOPS_MODEL_PROVIDER`. Only
`ollama` exists; a hosted provider (e.g. Claude) is a new class implementing
the same contract — no worker/API/UI changes.

## Local model profile

| Role | Default | Env |
|---|---|---|
| Vision | `qwen2.5vl:3b` (~3.2GB) | `SMARTOPS_VISION_MODEL` |
| Text | `llama3.2:3b` (~2.0GB) | `SMARTOPS_TEXT_MODEL` |
| Timeout | 480s (CPU inference + first-load) | `SMARTOPS_MODEL_TIMEOUT_SECONDS` |

Memory reality: the vision model needs ~4GB free inside the Docker VM at
inference time. On smaller VMs Ollama OOM-kills the runner; SmartOps then
produces honest `human_review` incidents with `reviewNotes` like
"VLM review failed: HTTPStatusError". Fixes: raise Docker Desktop memory
(≥10GB recommended), or set `SMARTOPS_VISION_MODEL=moondream` (~1.7GB,
weaker reasoning). `OLLAMA_MAX_LOADED_MODELS=1`, `OLLAMA_NUM_PARALLEL=1`,
and `OLLAMA_KEEP_ALIVE=2m` are set in compose to minimize pressure.

## Model upgrade path

1. Bigger local models: change the two env vars (e.g. `qwen2.5vl:7b`).
2. GPU: point Ollama at a CUDA runtime; detector backend `cuda`/`onnxruntime`.
3. Hosted APIs: implement a provider class; keep the same normalized
   incident schema. No frontend involvement, ever.
