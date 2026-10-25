# SmartOps handoff — 2026-10-25

Goal: implement all of GOAL_PROMPT.md. This is not demo-ready.
Branch: codex/smartops-live-demo. No push or PR authorized.

## Completed and verified

Phase 0 audit is in docs/AUDIT.md, commit 0003037. The reported original
startup crash and browser playback hang were not reproduced. Native Qwen
loading failed after 180 seconds, requesting 9.9 GiB with default batching.
There is no successful GPU inference benchmark yet.

Phase 1 removes runtime mock data, template AI briefings, failure-generated
incidents and catalog narratives. Model/detector failures are visible as
review_unavailable telemetry (ADR 0006). Failed writes cannot create local
success. Session changes clear data; API loss shows Offline and retries.
SSE routing is fixed, and startup failures retain their traceback logging.

The frontend is non-root Next.js standalone production. Earlier measured
memory after navigation was 44 MiB versus 973 MiB for the audited dev process;
this is not a soak result. Incident evidence no longer falls back to the whole
source video or reloads on source-health changes. Legacy /v1/cameras,
bootstrap.cameras, cameraId and frontend camera record aliases are removed.

Three fresh-volume down -v/up cycles passed: 24.00, 23.49 and 23.95 seconds
from up through HTTP checks. Each verified login, source/bootstrap contracts,
SSE snapshot, frontend and zero seeded incidents. Evidence/logs are in
`docs/verification/cold-starts.json` and adjacent logs. This does not verify
model readiness, sustained streaming, or the later 90-second demo target.
Prior database/evidence are backed up locally in sample-data/output/backups
(ignored by Git). The active database is fresh; historical fabricated rows
were removed by the resets. Supabase and native Ollama were not modified.

Next.js and eslint-config-next are 16.4.3. Patched compatible dependencies
produce zero npm audit findings. npm 11.4.2 crashed in Arborist peer resolution;
`npx --yes npm@11.6.2 audit fix` succeeded without changing global npm.
Docker npm ci/build also succeeded with the resulting lockfile.

Checks: API 23, orchestrator 11, worker 9, frontend 7 tests pass. ESLint,
TypeScript, local production build and Docker production build pass. Worker
and frontend tests need normal temp access on this Windows sandbox. API
on_event and LangGraph deserialization deprecation warnings remain.
Real service check confirms missing-frame review creates no incident.

## Remaining work

Phase 2 is in progress. MediaMTX and a single continuous RTSP processor now
run real YOLO/ByteTrack, polygon count/dwell, schedules, unattended bags and
blocked-exit rules. Rule incidents persist before any AI work. SQLite delivery
and evidence journals survive restart; missing post-event footage times out.
Real clips encode from a bounded ring and upload to MinIO. Evidence decoding
verified a 9.70-second / 30-frame clip. Stream recovery measured 8.36 seconds.
The engineering full-frame restricted zone is deliberately a wiring test, not
an actual security violation. Remove its history before client demos.

A sampled camera preview at /cameras has actual matching detections, zones and
anonymous track IDs. It explicitly does not claim full-rate live video. Five
live API samples measured 0.40–0.49 seconds age (live-observations.json).
API 24 and stream 18 tests pass; frontend lint/typecheck/production build pass.
Full-rate WebRTC, multi-source supervision, health classification and the
three-stream soak are not yet verified. The existing file window pipeline
still runs and needs retirement after stream source management is complete.
Native Ollama GPU inference and enrichment remain unverified.

Tenant isolation, auth hardening, zone editing, real notifications/reports,
phone onboarding, async enrichment, 3-stream
soak and full repeated demo E2E are still pending. SSE currently accepts a
long-lived token in its URL; do not publish raw browser/network logs.

The user must eventually provide event footage or approve licensed footage,
Telegram credentials/chat ID, and optional prospect branding. Ask these as
one batch when needed. Never change .wslconfig without the user's approval.

GOAL_PROMPT.md and SPI Material Tracking Handbook.pdf are user-owned untracked
files. Do not include them in commits. Keep the goal active until every
required acceptance gate is satisfied.
