# ADR 0001: Docker-first local development

**Status**: accepted

## Context
SmartOps spans seven custom services plus Postgres, Redis, MinIO, and
Ollama. Contributors run Windows, macOS, and Linux; host-installed
databases and Python environments drift immediately.

## Decision
All backend development and verification happens through Docker Compose.
Services get their own image and per-service build context; infrastructure
uses official images with named volumes; every service exposes a
healthcheck and `depends_on` uses `service_healthy` conditions. Host-side
tooling is limited to Node (frontend dev/tests) and an optional Python venv
for fast unit tests.

## Consequences
- `docker compose up --build` reproduces the entire product anywhere.
- Compose maps 1:1 to future Kubernetes objects.
- Cost: Docker VM resources bound the local AI profile (see ADR 0003 and
  docs/AI_PIPELINE.md memory notes); image builds (torch CPU) are large.
