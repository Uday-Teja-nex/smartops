# SmartOps Production Plan

## Purpose

Project-level execution plan for SmartOps: a production-shaped, multi-tenant
SaaS-style smart-building CCTV operations platform. This file tracks where
the system is and what comes next. Deep detail lives in `docs/`
(start with `docs/ARCHITECTURE.md` and `docs/AGENT_HANDOFF.md`).

Constraint set this plan is written for:

- local development first (Docker Compose), one MP4 source for testing
- multi-building / multi-source / multi-tenant architecture from day one
- local open-source models by default, provider abstraction always
- no fabricated AI output anywhere — simulated or rule-based paths are labeled

## Current state (2026-07-07) — implemented and verified

The platform is feature-complete for the local milestone:

- **Data**: multi-tenant Postgres schema (organizations, users/roles,
  buildings/floors/zones, sources, detections, incidents, audit events,
  comments, evidence items) with Alembic migrations. `docs/DATA_MODEL.md`.
- **Auth/RBAC**: JWT login, role ladder admin/supervisor/operator(+security,
  ehs)/viewer, internal service token for the pipeline, audit trail with
  real actors, seeded demo users.
- **Source management**: CRUD + pause/resume/disable + health reporting +
  detection config; UI page with add/edit drawer; MP4 autodiscovery.
- **Ingestion**: adapter architecture (`mp4` fully working; `rtsp`/`onvif`/
  `webrtc` are explicit interface-only stubs), health probes, candidate
  windows with Redis dedupe. `docs/VIDEO_PIPELINE.md`.
- **Detection**: YOLOv8n CPU detector service with pluggable backend
  registry; detections persisted with normalized bboxes; worker-side gating
  so VLMs only see interesting windows.
- **Orchestration**: LangGraph with 6-category taxonomy, Ollama structured
  outputs + Pydantic validation, confidence policy, human-review routing,
  rule-based System Health incidents. `docs/AI_PIPELINE.md`.
- **Evidence**: MinIO (S3-compatible) snapshots/thumbnails/ffmpeg clips,
  presigned URLs via a single API choke point, UI player with real
  detection overlays only.
- **Realtime**: Redis pub/sub → SSE (snapshot + granular incident/source
  events) → live UI upserts.
- **UI**: dark premium glassmorphism design system, 11 routes incl.
  Monitoring (pipeline telemetry), Incident Detail (evidence player,
  timeline, comments, SLA countdown, model metadata), Settings, Login.
- **Ops**: healthchecks + startup ordering, `.env.example`, structured JSON
  logs, request IDs, Prometheus `/metrics`, CI workflow, pytest/vitest
  suites, `scripts/smoke.py` E2E.

End-to-end verified live: MP4 source → 4 candidate windows → 22 YOLO
detections persisted → LangGraph review → MinIO evidence → incident with
audit trail → SSE delivery. Retry/dead-letter path exercised. Low-memory
VLM failure correctly produced `human_review` incidents with reasons.

## Target architecture

`source adapters → video-ingest → Redis queue → worker → YOLO detector →
LangGraph orchestrator → Ollama (or hosted provider) → API/Postgres/MinIO →
Redis pub/sub → SSE → Next.js console`

See `docs/ARCHITECTURE.md` for the full diagram and service table.

## Non-negotiables (unchanged)

Docker-first · service boundaries · multi-source design · provider
abstraction · event-driven, persistence-before-broadcast · durable audit ·
privacy-aware evidence access · no fake "live AI" claims.

## Next phases

### Phase A — Real camera transport (top priority)
- RTSP adapter (probe + rolling live windows), soak-tested against
  `mediamtx` or real hardware; then ONVIF discovery → RTSP delegation.
- Done when: an RTSP feed streams through the identical downstream pipeline.

### Phase B — Tenancy & privacy hardening
- Per-org query scoping from the JWT principal; building-scoped roles.
- Evidence access rules + access audit at `/v1/evidence/{id}/url`.
- Retention policies (evidence lifecycle, resolved-incident archival).

### Phase C — Deployment
- Secrets management, TLS ingress, migration-as-release-step, scheduled
  backups, monitoring/alerts on `/metrics` + dead-letter depth.
- Full checklist: `docs/DEPLOYMENT_READINESS.md`.

### Phase D — Model quality
- Hosted provider class (same `ModelProvider` contract) for accounts that
  opt in; GPU/ONNX detector backend; per-category threshold tuning from the
  Settings page values.

## Documentation maintenance policy

Update this file plus the relevant `docs/*` file in the same change that
alters service boundaries, provider strategy, schema direction, deployment
topology, or LangGraph responsibilities. `docs/AGENT_HANDOFF.md` must always
reflect the latest verified state.

## Success criteria for the current milestone — met

- [x] `docker compose up --build` starts the full stack
- [x] multiple video sources manageable from the UI
- [x] MP4 ingestion from configured sources (not hardcoded files)
- [x] YOLO candidate detection before VLM review, persisted with bboxes
- [x] incidents in Postgres with lifecycle, evidence, source, model, and
      detection metadata
- [x] Live Ops updates via push (pub/sub-backed SSE)
- [x] evidence player shows real backend-driven overlays
- [x] auth/RBAC foundation with role-gated UI and API
- [x] tests + lint + build + CI
- [x] docs for future agents (`docs/` set + ADRs)
