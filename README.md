# SmartOps

Production-shaped, multi-tenant smart-building CCTV operations platform.
SmartOps ingests video sources, runs lightweight YOLO detection, reviews
candidate events with local open-source VLM/LLM models (LangGraph +
Ollama), persists incidents with object-storage evidence, and streams live
updates to a dark, premium operator console.

**Honesty by design**: nothing in the UI is presented as AI detection unless
it came from the real pipeline. Fallbacks are routed to human review with
recorded reasons; rule-based incidents are labeled `rule-engine`; the
evidence player only draws persisted detection boxes.

## Quick start

```bash
# 1. Put any .mp4 into sample-data/input/
# 2. Start the stack (Docker Desktop with ≥10GB memory recommended for the VLM path)
docker compose up --build -d

# 3. First time only: pull the local models (~5GB)
docker exec smartops-ollama ollama pull qwen2.5vl:3b
docker exec smartops-ollama ollama pull llama3.2:3b
```

Open http://localhost:3000 — sign in with `operator@smartops.local` /
`smartops-demo` (all demo roles listed on the login screen).

Within a couple of minutes the seeded/autodiscovered MP4 source produces
candidate windows → YOLO detections → LangGraph review → incidents with
evidence, live on the dashboard.

Full setup, verification checklist, troubleshooting, backup/restore:
[docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md).

## Stack

Next.js 16 · React 19 · Tailwind 4 · framer-motion — FastAPI · SQLAlchemy ·
Alembic — Postgres · Redis · MinIO — ultralytics YOLOv8n — LangGraph —
Ollama (`qwen2.5vl:3b`, `llama3.2:3b`) — Docker Compose.

## Documentation

| Doc | What |
|---|---|
| [PLAN.md](PLAN.md) | Execution plan, current verified state, next phases |
| [SKILLS.md](SKILLS.md) | Engineering contract (principles, definition of done) |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System diagram, services, data flow |
| [docs/VIDEO_PIPELINE.md](docs/VIDEO_PIPELINE.md) | Adapters, candidate windows, gating, evidence |
| [docs/AI_PIPELINE.md](docs/AI_PIPELINE.md) | YOLO → LangGraph → models, validation, fallbacks |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | Entities and relationships |
| [docs/API_CONTRACTS.md](docs/API_CONTRACTS.md) | REST/SSE contracts with examples |
| [docs/UI_REVAMP_GUIDE.md](docs/UI_REVAMP_GUIDE.md) | Design tokens, motion rules, components |
| [docs/TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md) | Test layers and commands |
| [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md) | Setup, checks, failures, resets |
| [docs/DEPLOYMENT_READINESS.md](docs/DEPLOYMENT_READINESS.md) | What must change before real customers |
| [docs/IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md) | How to extend safely |
| [docs/AGENT_HANDOFF.md](docs/AGENT_HANDOFF.md) | State + do-not-break rules for the next agent |
| [docs/DECISIONS/](docs/DECISIONS/) | ADRs |

## Verification

```bash
npm run lint && npm test && npm run build
# NOTE: run each service separately — their `app` packages collide in one process
python -m pytest services/api/tests -q
python -m pytest services/orchestrator/tests -q
python -m pytest services/worker/tests -q
docker compose up --build -d && python scripts/smoke.py
```
