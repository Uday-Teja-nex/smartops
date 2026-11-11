# Dependency audit

Last run: 2026-11-11. Tools: `pip-audit` (PyPI advisory DB + OSV) per service requirements file, `npm audit`.

## Python services: clean

| Service | Requirements file | Result |
|---|---|---|
| api + notifier | `services/api/requirements.txt` | No known vulnerabilities |
| orchestrator | `services/orchestrator/requirements.txt` | No known vulnerabilities |
| detector | `services/detector/requirements.txt` | No known vulnerabilities |
| video-ingest | `services/video-ingest/requirements.txt` | No known vulnerabilities |
| stream-processor | `services/video-ingest/requirements-processor.txt` | No known vulnerabilities |
| worker | `services/worker/requirements.txt` | No known vulnerabilities |

Upgrades made to get there (each release at least two weeks old when pinned):

| Package | From | To | Why |
|---|---|---|---|
| starlette | 0.41.3 (via FastAPI) | 1.10.0 | 7 advisories, fixed in 1.3.1 |
| fastapi | 0.115.5 | 0.161.1 | needed for Starlette 1.x |
| cryptography (api) | 44.0.0 | 50.0.2 | advisories fixed in 48.0.1, 49.0.0, 50.0.0 |
| pyjwt (api) | 2.10.1 | 2.15.1 | 16 advisories, fixed up to 2.15.0 |
| langgraph / langgraph-sdk | 0.2.53 / 0.1.74 | 1.2.15 / 0.4.10 | SDK advisory fixed in 0.4.4 |
| httpx (orchestrator, detector) | 0.28.0 | 0.28.1 | aligned with the API |

Verification on the upgraded packages: API 117 passed, orchestrator 48 passed, detector 10 passed, video-ingest 58 passed.
One API test inspected FastAPI's routing internals and was rewritten to walk included routers (FastAPI 0.16x wraps them).
The test JWT secret was lengthened to 32+ characters, the same minimum production enforces.

Re-run:

```bash
pip install pip-audit
pip-audit -r services/api/requirements.txt
```

## Frontend: production clean, dev tooling documented

`npm audit --omit=dev`: **0 vulnerabilities** (what ships in the Next.js standalone image).

`npm audit` (including dev): 8 moderate findings, one root cause: `minimatch` 7.0.0-11.0.0
(denial of service via glob-part amplification) inside `typescript-eslint` / `@typescript-eslint/*`, pulled in by
`eslint-config-next`. Accepted for now because:

- It is lint tooling only. It never runs in the product and only reads glob patterns from our own config.
- npm's suggested fix downgrades `eslint-config-next` to 15.x, which does not match Next.js 16.
- The forward fix is minimatch 11.x, a major bump under typescript-eslint. A stable typescript-eslint release that
  takes it (8.72.3) was still in alpha on 2026-11-10.

Revisit when typescript-eslint 8.72.3 or later is stable: update and re-run `npm audit`.
