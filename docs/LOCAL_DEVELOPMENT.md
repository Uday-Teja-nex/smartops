# Local Development

Docker runs the application services; native Windows Ollama is the configured
model endpoint. Node 22 and Python are used for development checks.

## Prerequisites

- Docker Desktop running. The audited VM has 4 GiB RAM and 2 GiB swap.
- Native Ollama on port 11434 for model reviews. Successful GPU inference and
  latency are not yet verified. Default Qwen loading failed in the audit.
- Failed model reviews produce unavailable telemetry, never invented incidents.
- No Windows or WSL memory configuration changes have been made.

## First run

```bash
# 1. Optional: copy env defaults (works without it)
cp .env.example .env

# 2. Put at least one MP4 into sample-data/input/  (spaces in names are fine)

# 3. Start everything
docker compose up --build -d

# 4. Pull the local models (first time only; ~5GB total)
ollama pull qwen2.5vl:3b
ollama pull llama3.2:3b
```

Open http://localhost:3000 and sign in with a demo account
(password `smartops-demo` for all):

| Email | Role |
|---|---|
| admin@smartops.local | admin |
| supervisor@smartops.local | supervisor |
| operator@smartops.local | operator |
| viewer@smartops.local | viewer |
| security@smartops.local | security |
| ehs@smartops.local | ehs |

## What happens automatically

1. API runs Alembic migrations and seeds demo org/users/topology/sources.
2. `video-ingest` autodiscovers MP4s in `sample-data/input/`, registers them
   as sources, probes health, enqueues candidate windows.
3. `worker` samples frames → YOLO detector → persists detections → LangGraph
   review → uploads evidence to MinIO → persists incidents.
4. The UI receives live `incident`/`source` events over SSE.

No incident latency guarantee has been established. Single-person windows are
currently gated out, and model failures produce no incident. Continuous rules
and asynchronous enrichment are pending phases.

## URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| API + docs | http://localhost:8000 · /docs · /metrics |
| Orchestrator | http://localhost:8100/health · /v1/graph |
| Detector | http://localhost:8200/health |
| MinIO console | http://localhost:9001 (smartops / smartopsminio) |
| Ollama | http://localhost:11434 |

## Startup verification checklist

```bash
docker compose ps                        # all services healthy
curl http://localhost:8000/health
curl http://localhost:8200/health        # detector model loaded
docker compose logs video-ingest --tail 5   # source_scanned events
docker compose logs worker --tail 5         # job_processed events
python scripts/smoke.py                  # full E2E path (needs running stack)
```

## Frontend development on the host

```bash
npm ci
npm run dev      # http://localhost:3000 against the dockerized API
npm run lint
npm test         # vitest
npm run build    # webpack build (see note)
```

Note: `npm run build` uses `next build --webpack` because Turbopack's native
binary crashes on some Windows machines; `npm run build:turbo` is available
where it works.

## Backend tests (host, no Docker needed)

```bash
python -m venv .venv && .venv/Scripts/pip install -r services/api/requirements.txt \
  -r services/worker/requirements.txt langgraph==0.2.53 pytest httpx

# NOTE: run each service separately — their `app` packages collide in one process
.venv/Scripts/python -m pytest services/api/tests -q
.venv/Scripts/python -m pytest services/orchestrator/tests -q
.venv/Scripts/python -m pytest services/worker/tests -q
```

## Common failures

| Symptom | Cause / fix |
|---|---|
| Pipeline reports `review_unavailable` | Inspect the actual detector/model error. Failed reviews create no incident. Native Ollama is the default; GPU inference is not yet verified. |
| `alembic` errors on startup after pulling new code | Old dev volume: `docker compose down -v && docker compose up -d --build`. |
| Evidence URLs 503 | MinIO not healthy yet, or bucket missing — restart API after MinIO is up. |
| Source stuck `offline` with `adapter not implemented` | RTSP/ONVIF/WebRTC are interface-only; use MP4 sources locally. |
| Console shows Offline | API or SSE unavailable. Real data and actions are hidden; the console retries automatically. |
| Windows: `npm run build` segfaults | Use the default script (webpack); Turbopack crash is a known local toolchain issue. |

## Logs & reset

```bash
docker compose logs -f worker            # structured JSON logs
docker compose logs -f api | grep request
docker exec smartops-redis redis-cli llen smartops:candidate_jobs
docker exec smartops-redis redis-cli lrange smartops:candidate_jobs:dead 0 5

# Re-process footage (clear window dedupe)
docker exec smartops-redis redis-cli --scan --pattern "smartops:candidate_dedupe:*" \
  | xargs docker exec smartops-redis redis-cli DEL

# Full reset (drops DB, evidence, models)
docker compose down -v
```

## Backup / restore

```bash
# Postgres
docker exec smartops-postgres pg_dump -U smartops smartops > backup.sql
docker exec -i smartops-postgres psql -U smartops smartops < backup.sql

# MinIO evidence (filesystem copy while stopped, or use `mc mirror`)
docker run --rm --volumes-from smartops-minio -v "$PWD":/backup alpine \
  tar czf /backup/evidence-backup.tgz /data
```
