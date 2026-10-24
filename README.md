# SmartOps

SmartOps is being rebuilt into a live camera-to-incident operations product.
It is not yet client-demo-ready. See [PLAN.md](PLAN.md) and [AUDIT.md](docs/AUDIT.md)
for the verified state and remaining acceptance gates.

## Current local setup (PowerShell)

Docker Desktop must be running. Keep ports 3000, 8000, 8100, 8200 and 9000–9001
available. This is the current development stack, not the final demo launcher.

```powershell
docker compose up --build -d
```

Open [SmartOps](http://localhost:3000). Development seed credentials:
`operator@smartops.local` / `smartops-demo`. Do not use these in production.
A fresh database seeds topology and users, not incident history.

The frontend runs a non-root production build with webpack. Unsupported mock
occupancy/cleaning metrics and template AI text are removed. API/stream failures
show an unavailable state; failed writes do not fabricate local success.

The legacy file processor still reads `sample-data/input/`. Failed model
reviews create no incident and retain failure reasons in pipeline telemetry.
Existing database rows from the previous fabricated fallback are not valid
incident history. A clean reset and real history generation remain required.

## Models

Default container endpoint: `http://host.docker.internal:11434`. Native Ollama
must be running and reachable from Docker. The audit's native Qwen load failed
under memory pressure; GPU inference and latency targets remain unverified.

Optional Docker Ollama uses profile `docker-ollama` and host port 11435. Set
`SMARTOPS_OLLAMA_HOST=http://ollama:11434` in `.env` before using that profile.

```powershell
docker compose --profile docker-ollama up --build -d
```

## Verification

```powershell
npm run lint
```

```powershell
npx tsc --noEmit
```

```powershell
npm test
```

Run Python services separately because their app packages collide:

```powershell
.\.venv\Scripts\python.exe -m pytest services/api/tests -q
```

```powershell
.\.venv\Scripts\python.exe -m pytest services/orchestrator/tests -q
```

```powershell
.\.venv\Scripts\python.exe -m pytest services/worker/tests -q
```

Runtime regression checks after rebuilding:

```powershell
.\.venv\Scripts\python.exe scripts/verify_phase1_services.py
```

See [AGENT_HANDOFF](docs/AGENT_HANDOFF.md) and `docs/verification/` for evidence.
Streaming rules, tenant enforcement, phone notifications, cold-start/reset gates,
full E2E and production deployment remain unfinished.
