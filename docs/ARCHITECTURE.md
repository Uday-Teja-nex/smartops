# SmartOps Architecture

SmartOps is a multi-tenant-ready smart-building CCTV operations platform. It
ingests video sources, runs lightweight YOLO detection, reviews candidate
events with local open-source VLM/LLM models orchestrated by LangGraph,
persists incidents with evidence, and streams live updates to a Next.js
operator console.

## System diagram

```
                          ┌─────────────────────────────────────────────┐
                          │                  frontend                   │
                          │        Next.js 16 · React 19 · :3000        │
                          └────────────┬───────────────▲────────────────┘
                                       │ REST (JWT)    │ SSE (snapshot + granular events)
                          ┌────────────▼───────────────┴────────────────┐
                          │                    api                      │
                          │  FastAPI · :8000 · Alembic · RBAC · /metrics│
                          └──┬─────────┬──────────┬─────────┬───────────┘
                             │         │          │         │
                     ┌───────▼──┐ ┌────▼────┐ ┌───▼────┐ ┌──▼───────────┐
                     │ postgres │ │  redis  │ │ minio  │ │  pub/sub     │
                     │  :5432   │ │  :6379  │ │ :9000  │ │ smartops:    │
                     │ (truth)  │ │ (queue) │ │(evidence)│ events      │
                     └──────────┘ └────▲────┘ └───▲────┘ └──────────────┘
                                       │          │
        ┌──────────────┐   candidate   │          │ snapshots/thumbnails/clips
        │ video-ingest │──── windows ──┘          │
        │ adapters:    │                    ┌─────┴─────┐
        │ mp4 ✓ rtsp ✗ │                    │  worker   │
        │ onvif ✗      │   BRPOP jobs ────▶ │ frames →  │
        │ webrtc ✗     │                    │ detect →  │
        └──────┬───────┘                    │ review →  │
               │ health reports             │ persist   │
               ▼                            └─┬───────┬─┘
          api /v1/sources/{id}/health         │       │
                                    ┌─────────▼──┐ ┌──▼───────────┐
                                    │  detector  │ │ orchestrator │
                                    │ YOLOv8n CPU│ │ LangGraph    │
                                    │   :8200    │ │   :8100      │
                                    └────────────┘ └──────┬───────┘
                                                          │ /api/chat
                                                    ┌─────▼─────┐
                                                    │  ollama   │
                                                    │ qwen2.5vl │
                                                    │ llama3.2  │
                                                    └───────────┘
```

## Services

| Service | Tech | Port | Purpose |
|---|---|---|---|
| `frontend` | Next.js 16, React 19, Tailwind 4, framer-motion | 3000 | Operator console. JWT auth, SSE live updates, evidence player with real detection overlays. |
| `api` | FastAPI, SQLAlchemy 2, Alembic | 8000 | Source of truth. Auth/RBAC, sources, incidents, detections, evidence presigning, org settings, pipeline status, SSE fanout, `/metrics`. |
| `video-ingest` | Python | — | Reads registered sources from the API, probes health via source adapters, splits footage into candidate windows, enqueues jobs to Redis. |
| `worker` | Python, OpenCV, ffmpeg | — | Consumes candidate jobs: samples frames in the window, calls detector, persists detections, gates, calls orchestrator, uploads evidence to MinIO, persists incidents. Retries + dead-letter. |
| `detector` | FastAPI, ultralytics YOLOv8n (CPU) | 8200 | Stateless object detection on frames. Backend abstraction for ONNX/OpenVINO/CUDA/remote later. |
| `orchestrator` | FastAPI, LangGraph | 8100 | Event brain: classify candidates into the 6-category taxonomy via VLM, summarize via LLM, apply confidence policy, route to operations / human review / ignore. |
| `postgres` | Postgres 16 | 5432 | Durable storage (see docs/DATA_MODEL.md). |
| `redis` | Redis 7 | 6379 | Candidate job queue, dead-letter queue, candidate status keys, realtime pub/sub channel. |
| `minio` | MinIO | 9000/9001 | S3-compatible evidence storage (snapshots, thumbnails, clips). |
| `ollama` | Ollama | 11434 | Local model runtime. Default: `qwen2.5vl:3b` (vision), `llama3.2:3b` (text). |

## Data flow (happy path)

1. A supervisor registers a source in the UI (or `video-ingest` autodiscovers
   an MP4 in `sample-data/input/`).
2. `video-ingest` probes the source with its adapter, POSTs health to the API
   (which publishes a `source` event to Redis pub/sub → SSE → UI pulse), and
   enqueues deduplicated candidate windows.
3. `worker` samples N frames within the window, POSTs them to `detector`.
4. Detections (label, confidence, normalized bbox, frame ts) are persisted
   via `POST /v1/detections`.
5. Gate: windows with nothing detected are dropped; single-person-only
   windows are dropped; crowds and object hints go on.
6. `orchestrator` runs the LangGraph: VLM classification (structured JSON,
   Pydantic-validated) → LLM summary → policy (confidence threshold, SLA).
7. `worker` uploads snapshot/thumbnail/clip to MinIO, registers evidence
   items, then persists the incident draft via `POST /v1/incidents`.
8. The API publishes an `incident` event to Redis pub/sub; the SSE endpoint
   fans it out; the UI upserts the incident live.

## Honesty guarantees

- Unsupported adapters (RTSP/ONVIF/WebRTC) report explicit
  `adapter not implemented` health; they never fake ingestion.
- If the detector is down, candidates route to **human review** with a note —
  footage is never silently dropped, and detection is never simulated.
- If the VLM output is missing/invalid/low-confidence, the incident persists
  with status `human_review` and the reason in `reviewNotes`.
- Source-health incidents are labeled `modelProvider: rule-engine` — they are
  deterministic rules, not model output.
- The UI evidence player only draws bounding boxes from persisted detections;
  with none, it says "No detection overlay available".

## Realtime

`GET /v1/incidents/stream` (SSE, token via query param):
- `snapshot` event on connect: `{incidents: [...], sources: [...]}`
- `incident` events: single record on create/update
- `source` events: single record on health/lifecycle change
- heartbeat comments every 15s

Publishing happens in the API write paths through `app/events.py`
(best-effort; Postgres remains the source of truth).

## Auth model

- Users: JWT (HS256, `SMARTOPS_JWT_SECRET`), roles
  `admin > supervisor > operator/security/ehs > viewer`.
- Pipeline services: shared `X-Internal-Token` header → `service` principal
  (may write pipeline data, cannot act as an operator).
- SSE/`<video>` URLs accept `?token=` because those clients cannot set headers.

## Observability

- All Python services emit structured JSON logs (one object per line).
- The API adds `X-Request-Id` to every response, logs request summaries, and
  exposes Prometheus metrics at `/metrics`.
- Pipeline visibility: `GET /v1/pipeline/status` (queue depth, dead-letter
  count, recent candidate states) and the `/monitoring` UI page.

## Scaling path

- Every service is stateless except Postgres/Redis/MinIO → horizontal scaling
  of workers and detectors is a compose/k8s replica change.
- Provider abstraction (`orchestrator/app/providers/`) lets hosted VLM/LLM
  APIs replace Ollama by configuration.
- Detector backends (`detector/app/backends/`) allow ONNX/OpenVINO/CUDA or a
  remote inference endpoint without changing the worker contract.
