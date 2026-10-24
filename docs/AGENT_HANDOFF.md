# SmartOps handoff — 2026-10-24

Goal: implement all of GOAL_PROMPT.md. This is NOT demo-ready.
Branch: codex/smartops-live-demo. Phase 0 audit commit: 0003037.
See PLAN.md for remaining phases and docs/AUDIT.md for measured facts.

Current Phase 1 edits remove fabricated model-failure incidents and catalog
narratives/actions, repair SSE route ordering, preserve Alembic logger state,
and explicitly log startup failure tracebacks. Worker failures remain visible
as review_unavailable telemetry. ADR 0006 records this transition.

New regression tests failed before fixes. Current suites pass: API 23, orchestrator 11, worker 9. Docker rebuild is in progress.
Frontend has not yet been fixed or rebuilt: runtime mock metrics, fake local
write success, template AI text and stale live state still exist.

Runtime caveats:
- Docker images are old; source edits are not deployed until rebuilt.
- Existing frontend exited 137; cause unproven. Its development process had
  reached 973 MiB after browser navigation.
- Native Ollama Qwen default-batch load failed at 9.9 GiB allocation, after
  180 seconds. Native model downloads completed; service was not running on
  October 24. Docker Ollama is stopped to prevent port-11434 ambiguity.
- Fresh smartops_audit Postgres database migrated and seeded successfully.
  Original boot crash-loop was not reproduced. Cold-start gates remain open.
- Browser clip playback and direct incident navigation worked in the audit;
  reported ORB/session hang not reproduced. Evidence reload dependency remains.
- Existing database contains fabricated incidents from the old pipeline.
  Do not present them as valid history; clean reset is required later.
- Supabase containers belong to another project and must not be modified.

Verification evidence is under docs/verification. Baselines: lint/typecheck
passed, frontend 7 tests, API 21, orchestrator 11, worker 7. New tests increase
API and worker counts; use current test output for final results.

No PR or push authorized. User prompt and unrelated PDF are untracked; do not
include the PDF in implementation commits. Browser raw diagnostics are ignored
because request URLs may contain tokens. Save only curated evidence.

## Latest progress

Frontend mock data and template briefing removed. Housekeeping redirects to the
real incident filter. Failed writes no longer mutate local state; session changes
clear cached rows. Global offline state and automatic recovery verified by stopping
and restarting the real API. Frontend is non-root standalone production, 44 MiB
after navigation. Evidence reload no longer depends on source-health updates.
SLA durations use days and zero-count donut charts show an empty state.

Services rebuilt and runtime verified: SSE snapshot works and missing-frame review
creates no incident. Native Ollama is now the default compose endpoint; Docker
Ollama is optional on port 11435. Native reachability/inference remains unverified.

Remaining Phase 1: three cold starts; legacy camera aliases; remaining stale docs;
full browser workflow/error checks. Dependency audit found 19 vulnerabilities,
including critical Next.js: remediate before declaring demo/production readiness.
All future phases in GOAL_PROMPT.md remain required.
