# SmartOps handoff — 2026-10-26

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

## Phase 2 progress and current verification

Commit 5ecacd3 introduced continuous RTSP rules, evidence and sampled previews.
A bounded supervisor now discovers enabled RTSP sources with per-source
processes and durable journals. Three independent transports of the supplied
clip ran through real detection/tracking. This is a capacity test, not three
independently validated event scenes. Health rules measure missing frames,
low luminance, uniform images and unchanged images; the latter two explicitly
state possible causes rather than asserting deliberate tampering. Health
incidents now publish SSE updates after persistence.

The tuned soak stopped at 1190.14 seconds (19.8 minutes); it did NOT pass.
Median processing was about 3 FPS per stream, with 3/6/5 sampled intervals
below 2 FPS. Error counters did not increase during the run. Memory varied;
MinIO grew from 361 to 432 MiB, so a complete steady-state assessment remains
required. Full evidence and assessment are under docs/verification/stream-soak*.
Docker Desktop subsequently reported manually paused. The user has been
asked asynchronously to unpause it for runtime checks; keep developing the
independent parts without repeating that question.

Measured thread tuning retained detector resolution at 640, using two CPU
threads and serialized predictor initialization. Lower resolution changed
object counts and was not selected. Incident delivery now runs independently
of frame sampling to avoid stalls during bursts of evidence updates. Durable
acknowledgments cannot delete a newer pending update. These latest delivery
changes require another runtime soak after Docker resumes.

Direct MediaMTX WebRTC playback was verified in Edge at 960x544; capture-to-
display latency was not established (browser metadata omitted captureTime).
The integrated LiveVideo component, matched-frame mode and frozen-frame zone
editor are implemented and locally built, but their browser verification is
pending deployment. Playback currently supports managed MediaMTX RTSP paths;
external camera relay setup and media authorization are still pending.
Zone validation rejects invalid geometry, unknown rules and invalid schedules.
Source edits preserve configured zones. New evidence frames burn in their
actual detector boxes; decoding/browser verification of this latest path is
pending deployment. Old clips correctly retain their original metadata.

Local checks on 2026-10-26: API 33, stream 27, detector 1, frontend 8 tests
passed. Frontend lint, typecheck and production build pass, including the new
/sources/[id]/zones route. CI now includes stream and detector tests; no remote
CI claim is made because no changes have been pushed.

## Remaining work

Complete Phase 2 runtime verification, 30-minute three-stream soak, <=5-second
visible-event latency checks, and actual Tier 1 positive/negative footage
validation. Retire the old file-window pipeline once file publishing/source
management is unified. Native Ollama GPU inference, asynchronous enrichment,
provider/backend switches, tenant isolation, auth hardening, notifications,
reports, phone onboarding and repeated full demo E2E remain required.
SSE currently accepts long-lived tokens in URLs. MediaMTX ports remain
loopback-only. Do not treat this build as production-ready or client-demo-ready.

Footage shot list is in docs/FOOTAGE_SHOT_LIST.md. The existing clip is only
used for local engineering; commercial-demo rights are unverified. A batch
request for permitted event footage, Telegram credentials/chat ID and optional
branding was sent earlier; do not repeatedly ask. Never change .wslconfig
without the user's approval.

GOAL_PROMPT.md and SPI Material Tracking Handbook.pdf are user-owned untracked
files. Do not include them in commits. Keep working until the acceptance gates
are met; a completed increment is not a reason to stop the goal.
