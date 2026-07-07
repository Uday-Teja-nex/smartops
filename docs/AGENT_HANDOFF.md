# Agent Handoff

Concise state-of-the-world for the next AI agent or developer.
Read `PLAN.md`, `SKILLS.md`, `docs/ARCHITECTURE.md`, then this.

## Current status (2026-07-07)

Working, verified end-to-end on the local Docker stack:

- Multi-tenant schema + Alembic migrations (verified on Postgres 16).
- JWT auth + RBAC (admin/supervisor/operator/viewer/security/ehs) with
  seeded demo users; service-to-service internal token; audit trail with
  real actors.
- Source management: CRUD + pause/resume/disable + adapter health, UI page,
  MP4 autodiscovery. RTSP/ONVIF/WebRTC are honest interface-only stubs.
- Pipeline: MP4 → candidate windows → YOLO detector (yolov8n CPU) →
  persisted detections → LangGraph review (6-category taxonomy, structured
  outputs, Pydantic validation, confidence policy) → MinIO evidence
  (snapshot/thumbnail/ffmpeg clip, presigned URLs) → incident upsert →
  Redis pub/sub → SSE → UI live update. Retry + dead-letter verified live.
- Rule-based System Health incidents on source failure (`rule-engine`).
- UI: dark glass design system, 11 routes, evidence player with REAL
  detection overlays only, role-aware nav and action gating.
- Tests: API (pytest+SQLite), orchestrator (FakeProvider), worker (gating/
  retry), frontend (vitest), `scripts/smoke.py` E2E; CI workflow.

## Known risks / sharp edges

1. **Ollama memory**: on Docker VMs <~8GB the vision model OOMs; incidents
   then persist as `human_review` with the reason in `reviewNotes`. This is
   designed degradation, not a bug. (docs/AI_PIPELINE.md → memory profile.)
2. **Turbopack on Windows**: `next build` (turbopack) segfaults on some
   machines; `npm run build` is pinned to `--webpack`.
3. **Org scoping**: `org_id` exists everywhere but queries are not yet
   filtered per-principal (single-tenant runtime). See DEPLOYMENT_READINESS.
4. **Legacy `/v1/cameras`** endpoints and the incident `cameraId` alias are
   transitional; remove once nothing references them.
5. First VLM call after idle is slow (model load) — worker/orchestrator
   timeouts are deliberately generous (480–540s).

## Do-not-break rules

- Never fake AI output. Fallbacks must set `human_review` + `reviewNotes`;
  rule-based incidents must say `modelProvider: rule-engine`; the UI never
  draws boxes that aren't persisted detections.
- Persist before broadcast. Incidents only via `POST /v1/incidents`.
- Keep provider/detector/adapter abstractions intact.
- New env vars go to `.env.example` + `docker-compose.yml`.
- Schema changes = new Alembic revision.
- Keep `PLAN.md`, `SKILLS.md`, and this file current in the same PR.

## Verification commands

```bash
npm run lint && npm test && npm run build
# NOTE: run each service separately — their `app` packages collide in one process
python -m pytest services/api/tests -q
python -m pytest services/orchestrator/tests -q
python -m pytest services/worker/tests -q
docker compose up --build -d && python scripts/smoke.py
```

## Recommended next tasks (in order)

1. RTSP adapter (`services/video-ingest/app/adapters/rtsp.py`) against a
   real or simulated RTSP feed (e.g. `mediamtx` container) — the whole
   downstream pipeline already works.
2. Per-org query scoping derived from the JWT principal.
3. Evidence access rules (role × restricted) at `GET /v1/evidence/{id}/url`
   + access audit log.
4. Notification delivery (email/webhook) honoring stored org preferences.
5. Playwright E2E for login → source CRUD → incident detail.
