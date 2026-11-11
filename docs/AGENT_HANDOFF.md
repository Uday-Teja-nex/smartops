# SmartOps handoff

Updated 2026-11-11. Branch `codex/smartops-live-demo`; nothing is pushed.
Goal: `GOAL_PROMPT.md`. Phase status: `PLAN.md`. Evidence:
`docs/verification/`. Decisions: `docs/DECISIONS/` (ADRs 0001–0014).

## How to run it

```powershell
.\demo.ps1 up
```

`up` repairs Docker Desktop's stale sockets if needed, starts and warms
native Ollama when it's the provider or fallback, starts the stack, and
prints READY. A warm start takes 7–30 s; the first start of the day takes
about 2.5 minutes while the local model loads. `preflight`, `reset` (about
8 s), `status`, `backup`, `restore` and `fix-docker` are described in the
README. The client demo is `docs/presentation/PRESENTATION_SCRIPT.md`.

`.\demo.ps1 build-history` (about 27 min, once) replays each camera's
recorded clip through the real detector, tracker and rules at virtual times
over the last 3 days of business hours (`-Days`, `-Sessions`) and exports
the result as a snapshot. Every `reset` then restores it, shifted to end at
the reset, so the KPIs and reports have days of data. The current snapshot
(built 2026-11-11): 45 incidents, 180 timeline events, every one with its
clip and thumbnail; reset restores it in under 1 s. History incidents are
badged "Demo history", never notified or sent to the AI model, and operator
actions on them are labelled "Scripted demo action" in the timeline.

## Acceptance evidence

| Gate | Result | Evidence |
|---|---|---|
| Section C demo script, 5× from reset | **Passed 5/5 on the current stack** (attempt 8, 2026-11-11, with demo history loaded): 9/9 Playwright steps each, 120–277 s per run, 57/58 live evidence clips ready (one honest "Incomplete pre/post-event footage" refusal), 0 DB pool errors. Attempts 1–7 after the upgrades failed once each; every failure is archived with its cause and fix (see below). The earlier 5/5 (2026-11-06) predates the upgrades. | `e2e/five-runs-final/`, `e2e/five-runs-final-attempt1..7/`, `e2e/five-runs/` |
| Live push ≤ 5 s | 0.3–3.0 s from the triggering frame to the open Live Ops page across the 5 runs | `e2e/five-runs/measurements-*.json` |
| AI review ≥ 95 % validated, p95 ≤ 30 s | **Hosted** (`nemotron-3.5-super-vl:free`): 11/11, p95 10.1 s. **Local CPU only** (`qwen2.5vl:3b`, 320 px, 4 threads): 11/11, p95 34.2 s; misses the 30 s target by about 4 s when incidents coincide. | `enrichment-live-384px.json`, `enrichment-live-local-320px.json` |
| Honest AI failures | every failure names its cause; the incident stands without a review | API/orchestrator tests, E2E step 4 |
| Tenancy and roles | cross-workspace 404, viewer 403 (API and UI) | API tests, E2E steps 6–7 |
| Notifications | webhook delivered end to end in 1.0 s with a valid HMAC; a real crowding incident accepted by Telegram for the owner's chat 2.2 s after the rule fired (owner to confirm receipt) | `notifications-webhook.json`, `notifications-telegram.json` |
| Tier 1 on real footage | queue and crowding (store), crowding (mall atrium, office lobby), restricted entry (office, campus) | live incidents after reset; `sample-data/README.md` |
| Degraded states | detector and stream outages named with their impact; automatic recovery | `degraded-states.json`, E2E step 9 |
| Backup/restore | exact round trip; a restored clip downloads and decodes | `backup-restore.json` |
| Cold start, 3× | done in Phase 1 | `cold-starts.json` |
| Production rehearsal | HTTPS via Caddy, release-step migrations, first-admin bootstrap, secure cookies, SSE and evidence through the proxy, internal ports closed, dev secrets refused | `production-rehearsal.json` |
| 30-min 3-stream soak | **Passed:** min 2.73 fps, median 3.0, 0 failures, no memory growth. The baseline failed (local AI reviews starved the detector); fixed by capping review threads. | `stream-soak-final-assessment.json`, `stream-soak-baseline-assessment.json` |

Tests (2026-11-11): API 126, video-ingest 64, orchestrator 50, detector 10,
stream-publisher 3, worker 9, frontend 24, all on the pinned versions;
every CI job was run locally (`docs/verification/ci-local.md`). Lint and typecheck are clean. The
Playwright E2E needs the running stack (`npx playwright test`).

## Built this session (beyond the Phase 0–1 work)

- **Streaming:** one code path. `sample-data/streams.json` drives a
  publisher that loops each clip to a mediamtx path; the seed enables only
  cameras with footage. Rules have cooldowns, categories, readable
  summaries, and record the drawn zone.
- **Workspaces:** three seeded (office, mall, campus). Platform admins
  create a branded client workspace in Settings in one step (accounts,
  floors/zones, optional copy of a recorded camera, phone slot). The header
  shows the workspace and its colour.
- **Phone cameras:** "Add phone camera" creates the camera and shows an RTMP
  URL on the laptop's Wi-Fi address. LAN clients may only publish to
  `phone-*` paths with a publish-only credential and cannot watch.
  **Not yet tried with a real phone.**
- **Auth:** 15-min tokens bound to revocable sessions, rotating HttpOnly
  refresh cookie, argon2id, throttling (ADR 0012).
- **Notifications:** Telegram + webhook outbox (ADR 0013). Telegram verified
  with the owner's bot; the channel is paused after the test.
- **AI review:** scene, verdict, model name and latency; specific failure
  reasons; optional native-Ollama fallback; 384 px clean frames; background
  model loading; shared runner options (ADR 0014).
- **Operations:** `/v1/system/status` with an app-wide degraded banner and
  a Monitoring services panel; `/ready`; backup/restore; Caddy production
  overlay; CUDA and remote detector backends; non-root images.
- **Footage:** three Pexels clips (licence in `sample-data/README.md`) for
  the office lobby, mall atrium and campus lab cameras; camera stability was
  measured before use.
- **Rules on real crowds:** crowding/queue count raw detections (ByteTrack
  could not confirm small people in a dense crowd at 3 fps: 0 of 45 frames
  over the limit vs 34 raw), with 1.5 s flicker tolerance; cooldowns apply to
  every rule type.
- **Local AI capacity:** one local review at a time; at most one per camera
  per 120 s on the laptop (`SMARTOPS_REVIEW_MIN_INTERVAL_SECONDS`); skipped
  reviews say why. Smaller models were benchmarked and rejected
  (`review-model-benchmark.json`).
- **Pages cut:** Safety and Occupancy dashboards counted incident types the
  pipeline never produces; they now redirect to filtered Live Ops.

## Built 2026-11-11 (client-IT items and hardening)

- **Secrets at rest:** notification credentials are Fernet-encrypted under
  `SMARTOPS_SECRETS_KEY` (generation command in `DEPLOYMENT_READINESS.md`).
- **Users:** admins add, deactivate, re-role and reset the password of users; everyone can change
  their own password. Sessions are per tab, and ended sessions are pruned
  after 7 days.
- **Retention:** per-workspace evidence retention (default 30 days) with an
  audited purge. The demo-history snapshot (`history/` in MinIO) is exempt.
- **Metrics:** Prometheus `/metrics` on the API, orchestrator and detector.
  `GET /v1/system/metrics` turns them into p50/p95 latency and outcome
  shares for the Monitoring page, or says "metrics unavailable (reason)".
- **Privacy:** a "How SmartOps handles data" page is linked from the
  console footer.
- **Dependencies:** fastapi 0.161 / starlette 1.10, cryptography 50, pyjwt
  2.15, langgraph 1.2, httpx 0.28.1 everywhere. `pip-audit` is clean;
  `npm audit` is clean for production
  (`docs/verification/dependency-audit.md`).
- **AI fallback breaker:** after 2 failed hosted requests the hosted model
  is skipped for `SMARTOPS_FALLBACK_COOLDOWN_SECONDS` (300). One probe is
  then allowed, and Monitoring says it is paused. Before this, every review
  paid the hosted timeout before falling back (85–136 s on CPU).

## What the E2E gate attempts found (all fixed)

| Attempt | Failure | Cause | Fix |
|---|---|---|---|
| 5 | evidence "capture gap" | the evidence ring was fed by the detection loop, so it starved while the detector was slow | `RingSampler`: a per-camera thread feeds the ring at 3 fps independently |
| 6 | QueuePool exhausted | FastAPI ≥ 0.118 keeps yield dependencies open for the whole response, so every open SSE stream held a DB connection through auth | auth opens and closes its own session |
| 7 | step 4 timed out at 90 s | CPU-fallback reviews waited for the hosted timeout first | circuit breaker; the step waits the stated 180 s bound |
| history | 9/54 clips failed | office-lobby restricted entries fired on a session's first frame, before any pre-event footage existed | rules start after 5 s of footage; sessions also join the loop part-way and run on until each event has its post-roll |

## Findings worth knowing

- Docker Desktop 4.76 leaves AF_UNIX socket files behind on every stop and
  then crash-loops on start. `demo.ps1 up` repairs this automatically.
- `qwen2.5vl:3b` can't use the 4 GB GPU (0/37 layers offloaded); it runs on
  CPU and commits about 13.5 GB while loaded.
- Ollama reloads a model when runner options differ. Warm-up, background
  loads and reviews must share `num_ctx 2048, num_batch 32`, otherwise every
  warm-up is wasted.
- The OpenRouter free tier allows 50 requests a day; E2E runs use it up
  quickly. The local fallback then takes over at about 20 s per review.
- Login throttling (5 per account per minute) applies to scripted tests
  too; the E2E signs in once per account.

## Known limitations and what I couldn't verify

- **Footage gaps:** unattended bag, blocked exit, loitering and after-hours
  entry are unit-tested on synthetic tracks only; no licensed stock footage
  exists, so the owner needs to record them. The store clip's licence is
  still undocumented.
- **Owner-dependent:** real phone camera; confirming the Telegram messages
  arrived.
- Local CPU AI review misses p95 ≤ 30 s (34 s) when incidents coincide; the hosted model passes.
- `npm audit`: 8 moderate findings in the ESLint dev toolchain (minimatch);
  production dependencies are clean.
- CI has not run on the upgraded dependencies: nothing is pushed.
- `SMARTOPS_SECRETS_KEY` is an env var; a cloud deployment should hold it
  in a secrets manager, and rotating it means re-encrypting the channels.
- No email invites or SSO yet; an admin passes on a generated temporary
  password.
