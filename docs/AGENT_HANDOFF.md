# SmartOps handoff — 2026-10-26

Goal: implement all of GOAL_PROMPT.md. This is not demo-ready.
Branch: codex/smartops-live-demo. No push or PR authorized.

## Completed and verified

Phase 0 audit is in docs/AUDIT.md, commit 0003037. The reported original
startup crash and browser playback hang were not reproduced. Native Qwen
loading failed after 180 seconds, requesting 9.9 GiB with default batching.
A later small-batch native Qwen probe completed on CPU in 112.12 seconds (92.67 seconds loading). Two repeat loading attempts timed out at about 152 seconds. There is no successful GPU inference benchmark yet.

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
Docker Desktop was manually paused, then the user resumed it on 2026-10-26. The latest deployment succeeded. A new 30-minute measurement is running in stream-soak-delivery.json; it already has below-2-FPS samples and is not a pass. The legacy worker and video-ingest services were stopped to prevent competing old model loads.

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

### Stream credential and diagnostic isolation (2026-10-31)

SSE UI now obtains a 30-second, incident-stream-audience JWT ticket through an
authenticated POST. Long-lived query tokens are rejected on REST/SSE; legacy
local source clip URLs still accept them and remain a migration task. Streams
close after approximately one minute (plus a bounded Redis wait), forcing a
fresh ticket/account check on reconnect. Tickets may be reused within their
short expiry; they are not single-use. Browser reconnect acceptance is pending.
Pipeline diagnostics filter status rows by accessible source IDs; global queue
counts are null for user principals rather than exposing other tenants' totals.
Monitoring already renders unavailable counts as a dash. These changes are local,
not deployed; no Docker recovery attempted during this increment.

### Offline authentication and tenant boundaries (2026-10-30)

Docker recovery failed; user asked to work elsewhere. No further Docker work in
this increment. Local API work now resolves current user activity, role and org
from the database on every authenticated request. Human incident lifecycle actions
reject service tokens. Organization settings, buildings and user lists follow the
principal's workspace. New tenancy.py scopes request ORM reads for org-bearing
models; bootstrap, source, incident, evidence, detection and live routes use it.
SSE snapshots and incident/source fanout are org-filtered. Incident building must
match its source. This is partial hardening, not complete tenancy acceptance:
global pipeline status diagnostics, query-string access tokens, refresh/logout
revocation, comprehensive cross-org write/link tests and production config remain.
Redis publishing is mocked only in the local API test fixture, avoiding external
service hangs. No runtime mocks added. All changes still require deployment
verification when Docker recovers.

### Runtime follow-up (2026-10-30)

OpenRouter enrichment initially exhausted 512 tokens on optional reasoning and
returned empty content with finish_reason length. The deployed fix requests
reasoning effort none and 1024 output tokens. A saved-image enrichment then
returned validated observations/actions/limitations in 8.4 seconds; see
verification/openrouter-enrichment.json. Automatic reviews reached the shared
40-attempt cap on October 29; that budget was not reset or bypassed. Successful
automatic enrichment after this fix still needs live confirmation.

Three-minute smoke showed periods near 3 FPS but intermittent sub-2 FPS samples;
it is not acceptance. October 30 Docker container listing returns HTTP 500.
User was asked to restart Docker Desktop. Added configurable RTSP decoder thread
limit (default one, validated 1–16), pending deployment and comparison.
OpenCV 4.10 documents CAP_PROP_N_THREADS as an open-only FFmpeg property:
https://docs.opencv.org/4.10.0/d4/d15/group__videoio__flags__base.html
Reasoning budget reference:
https://openrouter.ai/docs/guides/best-practices/reasoning-tokens

### Authorized hosted configuration and enrichment (2026-10-29)

User explicitly authorized sending selected incident images with provider data
collection allowed. Parent scope/.env contains their key. Project ignored .env
now contains a local copy plus OpenRouter explicit nemotron free model IDs,
free-only true, data collection allow, local YOLO, and stream enrichment true.
Never print either env file or resolved Compose configuration.

Orchestrator deployment succeeded; saved engineering image review returned HTTP
200 in 4.31 seconds with no supported event. See openrouter-image-review.json.
This is connectivity/contract evidence, not accuracy acceptance. New enrichment
endpoint uses one call for supplemental observations/actions/limitations.
Stream integration queues bounded images in durable per-source journals after
evidence, waits for incident delivery, and uses a shared 40-attempt UTC-day budget.
No model result changes measured rule event fields. Deployment verification of
the new asynchronous path remains required. Previous statements below that
Docker is unavailable or continuous enrichment is unimplemented are historical.

### Hosted API increment (2026-10-29)

OpenRouter/OpenAI-compatible review adapter and optional Hugging Face object
detection adapter added with mocked contract tests and Compose configuration.
Local defaults unchanged. Setup is in FREE_API_SETUP.md. Actual .env credentials
were not read or changed. OpenRouter free-only defaults on; data collection
defaults deny; no paid fallback or automatic relaxation. Meta is not a verified
free API. Continuous async enrichment remains unfinished.

Browser access to the user's OpenRouter keys page was blocked by automatic
approval review's usage limit; do not bypass that origin gate using another
browser tool. User was asked to create the key manually and save it in .env.
Docker check October 29 failed because dockerDesktopLinuxEngine pipe was absent;
no containers were rebuilt or deployed in this increment. The prior delivery
soak finished but failed throughput and had timeout samples when Docker paused;
do not count it as Phase 2 acceptance.

Complete Phase 2 runtime verification, 30-minute three-stream soak, <=5-second
visible-event latency checks, and actual Tier 1 positive/negative footage
validation. Retire the old file-window pipeline once file publishing/source
management is unified. Native Ollama GPU inference, asynchronous enrichment,
provider/backend switches, tenant isolation, auth hardening, notifications,
reports, phone onboarding and repeated full demo E2E remain required.
SSE now uses 30-second audience-bound tickets and periodically reconnects.
Long-lived query credentials are rejected, including on local clip endpoints;
the unused frontend clip URL helper was removed. Ticket responses use no-store.
Local API suite passes (67), including streaming middleware and audit migration tests;
deployment and browser reconnect remain unverified.
Evidence URL issuance now requires a human user; restricted items require
operator level or higher. Issuance is persisted in tenant-scoped evidence_access
before returning a no-store response, without storing the signed URL. Migration
0002 upgrade/downgrade passed on SQLite; PostgreSQL deployment is still pending.
An issuance record proves authorization to retrieve, not an actual download.
Legacy incident thumbnail/clip URLs are no longer serialized; playback uses
the authorized evidence endpoint. Both incident views distinguish denied access,
missing clips, loading, and request failure. TypeScript passed; browser QA pending.
API production startup now rejects default/short JWT and internal secrets,
default/short enabled object-storage secrets, demo account seeding, and wildcard
or empty CORS allowlists. Validation tracebacks hide configuration input values.
This is API configuration validation, not a verified production deployment.
Login now uses shared Redis limits (5/account, 30/client address per minute),
returns 429 with Retry-After, and fails closed with 503 on Redis outages.
ADR 0011 records the tradeoffs; live Lua expiry/concurrency checks are pending.
API request bodies are bounded before routing, including chunked requests and
false Content-Length headers. Default 2 MiB, configurable through Compose with
SMARTOPS_REQUEST_MAX_BYTES (1 KiB–16 MiB). Evidence media is uploaded directly
to object storage; API requests contain metadata. Streaming responses are not
buffered by this middleware. Runtime load/stream reconnect validation is pending.
Evidence creation now rejects incident/source and incident/candidate mismatches.
Incident evidence and detection reads also require the incident's source, so
candidate IDs reused across cameras cannot mix their records (2026-11-01).
Incident replay now rejects attempts to bind an existing ID to a different
camera or candidate (409), leaving its data and audit trail unchanged. Valid
enrichment updates still preserve operator lifecycle state. Insert collisions
roll back before inspecting only the conflicting row's workspace ID: foreign
IDs return 404, same-workspace races return retryable 409. Regression tests
exercise the duplicate-key boundary and verify no duplicate creation audit;
true concurrent PostgreSQL load verification remains pending.

Continuous incident delivery now quarantines non-retryable HTTP rejections in
the per-source SQLite dead_letters table so later incidents can proceed.
Network failures, 401, 409, 429 and server errors still retry. Quarantine retains
the rejected payload/status and does not remove a newer pending update. AI
reviews wait while an incident has unresolved dead letters. Explicit
Outbox.replay_dead_letter(sequence) recovery refuses to overwrite pending data;
the recovery CLI now provides summary-only inspection and explicit replay.
See INCIDENT_RECOVERY.md. An operator UI remains unimplemented.
Video-ingest suite passes 41 tests; these changes are not deployed.
MediaMTX ports remain
loopback-only. Do not treat this build as production-ready or client-demo-ready.

Footage shot list is in docs/FOOTAGE_SHOT_LIST.md. The existing clip is only
used for local engineering; commercial-demo rights are unverified. A batch
request for permitted event footage, Telegram credentials/chat ID and optional
branding was sent earlier; do not repeatedly ask. Never change .wslconfig
without the user's approval.

GOAL_PROMPT.md and SPI Material Tracking Handbook.pdf are user-owned untracked
files. Do not include them in commits. Keep working until the acceptance gates
are met; a completed increment is not a reason to stop the goal.

## Latest verification and fixes (2026-10-26)

Zone editor drawing/save/reload/delete passed through the real browser and API;
see verification/zone-editor.json. The temporary no-rule zone was deleted.
Real evidence downloaded and decoded with visibly burned-in detector boxes.
One clip was only one second long: encoding backlog outlived the 12-second
ring. A regression now requires complete pre/post coverage and rejects capture
gaps; default retention is 32 seconds with the unchanged 16 MiB cap. Stream
suite passes 29 tests. These fixes are built but await deployment verification.

Integrated WebRTC played two of three tiles. The remaining tile reproduced a
Next Script concurrent-load callback race. LiveVideo now handles onLoad as
well as onReady with per-source script IDs; autoplay rejection has an actual
play button. Production rebuild and deployment passed. All three video elements reached readyState 4 at 960x544 with advancing playback. See webrtc-integrated.json/png. The screenshot also honestly shows stale detections during the loaded soak; smooth video does not prove detector throughput.
Frontend lint and TypeScript passed after the fixes.

Ollama requests now default to 30-second HTTP timeout, 2048 context, batch 32,
256 generated tokens and ten-minute residency. Invalid timeouts fail startup.
Orchestrator suite passes 17 tests. These changes are not GPU/latency acceptance
and are not yet deployed. See ADR 0008 and native-ollama verification reports.
