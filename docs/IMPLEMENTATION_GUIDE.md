# Implementation Guide (for future agents and developers)

Read first: `PLAN.md`, `SKILLS.md`, `docs/ARCHITECTURE.md`,
`docs/AGENT_HANDOFF.md`. Then this file for the how.

## Repository map

```
src/                     Next.js frontend (App Router)
  app/                   pages: / live-ops sources monitoring incidents/[id]
                         safety housekeeping occupancy reports settings login
  app/providers.tsx      SmartOps data context (bootstrap + SSE)
  app/auth.tsx           auth context (JWT, roles)
  components/            AppShell, EventTable, EvidenceVideoPlayer, charts, ui/*
  lib/                   api client, types, analytics, visuals, mockData (fallback only)
services/
  api/                   FastAPI + Alembic + tests (source of truth)
  orchestrator/          LangGraph + providers + catalog + tests
  worker/                queue consumer + detector client + evidence + tests
  video-ingest/          source adapters + scan loop
  detector/              YOLO service + backend registry
shared/schemas/          JSON Schema contracts (source, incident)
scripts/smoke.py         E2E smoke test against a running stack
docs/                    this documentation set + DECISIONS/ ADRs
```

## Coding standards

**Python services**
- Python 3.11, type hints everywhere, Pydantic for every wire contract.
- Structured JSON logs via each service's `log.py` (`log(event, **fields)`);
  never bare prints in new code.
- Config through `SMARTOPS_*` env vars with safe local defaults; every new
  var goes into `.env.example` AND `docker-compose.yml`.
- API: routers per resource in `app/routers/`, serializers in
  `app/serializers.py`, RBAC via `Depends(require_*)` from `app/auth.py`.
  Every mutating endpoint publishes realtime events where relevant and
  records audit entries for incidents.
- DB changes = new Alembic revision (never edit 0001, never rely on
  `create_all` outside SQLite tests).

**Frontend**
- Types in `src/lib/types.ts` mirror API responses (camelCase).
- All HTTP through `src/lib/api.ts` `request()` (adds JWT + error shaping).
- Pages are client components consuming `useSmartOps()` / `useAuth()`.
- Design system: use `components/ui/*` (GlassPanel, Button, Skeleton,
  EmptyState/ErrorState) and tokens from `globals.css` — no ad-hoc hex colors.
- Every data surface needs loading (Skeleton), empty (EmptyState), and error
  (ErrorState/banner) states.

## Service boundaries (do not blur)

- UI ↔ API only. The UI never calls detector/orchestrator/Ollama/MinIO
  directly (evidence flows through presigned URLs issued by the API).
- LangGraph = decisions (classification, policy, routing). Video transport,
  frame decoding, and detection loops stay in ingest/worker/detector.
- Model access only behind `ModelProvider`; detection only behind
  `DetectorBackend`.
- Incidents are only created/updated through the API (audit + realtime
  events depend on it).

## How to add things safely

**A new event type**: add to `orchestrator/app/catalog.py` (category,
subcategory, severity, SLA, copy) → it is automatically offered to the VLM
and validated. Update `shared/schemas/incident.schema.json` if you add a
category, plus `CATEGORY_COLORS` in `src/lib/visuals.ts` and the reports
trend map. Add a routing test.

**A new source adapter**: implement `SourceAdapter` in
`video-ingest/app/adapters/`, register it in `adapters/__init__.py`, keep
`probe()` honest about failures. UI/API need no changes (source_type is
already in the enum).

**A new detector backend**: implement `DetectorBackend` in
`detector/app/backends/`, wire it in `get_backend()`, select with
`SMARTOPS_DETECTOR_BACKEND`.

**A hosted model provider**: implement `ModelProvider` in
`orchestrator/app/providers/`, extend the factory, select with
`SMARTOPS_MODEL_PROVIDER`. Responses must satisfy the same schemas.

**A new API surface**: router + schemas + serializer + RBAC dependency +
tests + `docs/API_CONTRACTS.md` entry. If the frontend consumes it: types +
`api.ts` helper.

## Verification before calling anything done

```bash
npm run lint && npm test && npm run build
# NOTE: run each service separately — their `app` packages collide in one process
python -m pytest services/api/tests -q
python -m pytest services/orchestrator/tests -q
python -m pytest services/worker/tests -q
docker compose config --quiet
docker compose up --build -d   # then: python scripts/smoke.py
```

## Production-grade rules (non-negotiable)

1. Never present simulated output as model output — label rule-based and
   fallback paths (`modelProvider`, `reviewNotes`).
2. Persistence before UI broadcast; the UI renders only persisted state.
3. Multi-source, multi-tenant shapes in every new table/endpoint
   (`org_id`, `source_id` from day one).
4. Long-running work is queued and retryable, never inline in API requests.
5. Update `PLAN.md`/`SKILLS.md`/relevant docs in the same change that alters
   architecture — stale docs are treated as bugs.
