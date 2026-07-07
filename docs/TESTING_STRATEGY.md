# Testing Strategy

## Layers

| Layer | Location | Runner | Covers |
|---|---|---|---|
| Frontend unit | `src/**/*.test.ts` | `npm test` (vitest) | analytics aggregations, time-range filtering, SLA math |
| API integration | `services/api/tests/` | pytest + TestClient + SQLite | auth (login/JWT/internal token/SSE token), RBAC per role, sources CRUD + lifecycle + topology validation, health→rule-incident, incident lifecycle + audit trail + idempotent upsert + filtering |
| Orchestrator | `services/orchestrator/tests/` | pytest (FakeProvider, no Ollama) | graph routing: confident→active, low-confidence→human_review, invalid JSON→human_review, exception→human_review, no_event→ignored, detector-unavailable→human_review without VLM call, taxonomy completeness |
| Worker | `services/worker/tests/` | pytest (fake Redis) | detection summarization, gating rules, retry→dead-letter flow |
| E2E smoke | `scripts/smoke.py` | python, against running compose stack | login → source online → detections persisted → incident persisted → audit events → SSE snapshot |
| Build checks | — | `npm run lint`, `npm run build`, `docker compose config` | static + packaging health |

## Commands

```bash
npm run lint && npm test && npm run build
python -m pytest services/api/tests -q
python -m pytest services/orchestrator/tests -q
python -m pytest services/worker/tests -q
docker compose up --build -d && python scripts/smoke.py
```

## CI (`.github/workflows/ci.yml`)

Five jobs on push/PR: frontend (lint/test/build), api tests, orchestrator
tests, worker tests, compose config validation. The smoke test is not in CI
(needs the full Docker stack + models); run it locally before releases.

## Test design rules

- API tests run against SQLite (`SMARTOPS_DATABASE_URL=sqlite:///…`) — the
  app skips Alembic and uses `create_all` in that mode. Postgres-specific
  behavior must be verified via the compose stack.
- Orchestrator tests must never require Ollama: use `FakeProvider`.
- Every new event type / category needs: a catalog entry test, a routing
  test if it has special policy, and (if rule-based) an API test.
- Every new endpoint needs at least: a happy-path test, an RBAC test, and a
  404/422 test.
- Honesty regressions are test failures: e.g. detector-unavailable must
  route to human review, never to a confident incident.

## Future E2E

Browser-level tests (Playwright) for login → sources CRUD → incident detail
flows are the next investment once the UI stabilizes; the SSE and evidence
URL contracts are already covered at the API layer.
