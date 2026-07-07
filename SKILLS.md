# SmartOps Engineering Skills

Operational companion to `PLAN.md`: how this codebase is built and kept
production-grade. The detailed how-to lives in
`docs/IMPLEMENTATION_GUIDE.md`; this file is the contract.

## Project identity

SmartOps is a multi-service CCTV operations platform: video ingestion,
YOLO detection, LangGraph incident orchestration, operator workflows,
evidence handling, reporting. The dashboard is the visible tip; the product
is the pipeline plus the incident lifecycle.

## Approved stack

| Layer | Choice |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind 4, framer-motion |
| API | FastAPI + SQLAlchemy 2 + Alembic |
| Queue/state | Redis (lists for jobs, pub/sub for realtime) |
| DB | Postgres 16 (SQLite only inside unit tests) |
| Evidence | MinIO / any S3-compatible store, presigned URLs only |
| Detection | ultralytics YOLOv8n behind `DetectorBackend` registry |
| Orchestration | LangGraph (decisions only, never transport) |
| Models | Ollama behind `ModelProvider` (`qwen2.5vl:3b` vision, `llama3.2:3b` text) |
| Packaging | Docker Compose, per-service images, healthchecks |

LM Studio stays experimentation-only. Kubernetes when deployment demands it.

## Core principles

1. Local-first, never local-only.
2. Service boundaries: UI ↔ API only; model access behind providers;
   detection behind backends; transport in adapters.
3. Multi-source and multi-tenant shapes in every new table and endpoint.
4. Deterministic schemas over free-form model text — structured outputs +
   Pydantic validation on every model response.
5. Incidents are the core entity; they are created only through the API
   (audit + realtime depend on it); persistence precedes broadcast.
6. Anything long-running is queued and retryable (attempts → dead-letter).
7. **Honesty rule**: fallbacks route to `human_review` with reasons in
   `reviewNotes`; rule-based incidents say `modelProvider: rule-engine`;
   the UI never renders detection overlays that are not persisted
   detections; mock data is always labeled.

## Event processing order (fixed)

detection → model review → policy → persistence → realtime broadcast.
Every event carries `sourceId`/org metadata from the first step onward.

## Realtime rules

SSE from the API backed by Redis pub/sub (`smartops:events`): one snapshot
on connect, then granular `incident`/`source` events, heartbeats while
idle. REST for history and actions. The frontend never polls models.

## Definition of done

A change is done only when:

- it runs in Docker (`docker compose up --build`)
- config is explicit (`SMARTOPS_*` env + `.env.example` + compose defaults)
- `npm run lint && npm test && npm run build` pass
- `python -m pytest services/*/tests -q` passes
- it does not bypass provider/backend/adapter abstractions or persistence
- docs are updated when architecture moved (`PLAN.md`, relevant `docs/*`,
  `docs/AGENT_HANDOFF.md`)

## Security & privacy rules

CCTV data is sensitive: evidence access only via presigned URLs from the
API; operator actions audited; no identity recognition features; least
privilege for storage; secrets never in code (dev defaults are flagged in
`docs/DEPLOYMENT_READINESS.md`).

## Anti-patterns (rejected in review)

- backend logic in Next.js route handlers
- sending whole video streams to VLMs, or VLM calls on ungated windows
- LangGraph doing video transport
- model-specific response shapes leaking into the frontend
- evidence binaries in Postgres or app containers
- silent fallbacks that look like confident detections
- schema change without an Alembic revision
- new env var without `.env.example` + compose entry

## Maintenance rule

`PLAN.md`, this file, and `docs/AGENT_HANDOFF.md` are part of the project
contract. If implementation drifts from them, fix the code or fix the docs
in the same change — never let them become architecture fiction.
