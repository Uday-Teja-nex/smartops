# SmartOps handoff

Updated 2026-11-06. Branch `codex/smartops-live-demo`; nothing is pushed.
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

## Acceptance evidence

| Gate | Result | Evidence |
|---|---|---|
| Section C demo script, 5× from reset | **Passed 5/5** (9/9 Playwright steps each, real Edge, real stack). An earlier attempt failed once at the degraded-banner step; the step now checks the API first. | `e2e/five-runs/summary.json`, `e2e/five-runs-attempt1/` |
| Live push ≤ 5 s | 0.3–3.0 s from the triggering frame to the open Live Ops page across the 5 runs | `e2e/five-runs/measurements-*.json` |
| AI review ≥ 95 % validated, p95 ≤ 30 s | **Hosted** (`nemotron-3.5-super-vl:free`): 11/11, p95 10.1 s. **Local CPU only** (`qwen2.5vl:3b`, 320 px, 4 threads): 11/11, p95 34.2 s; misses the 30 s target by about 4 s when incidents coincide. | `enrichment-live-384px.json`, `enrichment-live-local-320px.json` |
| Honest AI failures | every failure names its cause; the incident stands without a review | API/orchestrator tests, E2E step 4 |
| Tenancy and roles | cross-workspace 404, viewer 403 (API and UI) | API tests, E2E steps 6–7 |
| Notifications | webhook delivered end to end in 1.0 s with a valid HMAC | `notifications-webhook.json` |
| Degraded states | detector and stream outages named with their impact; automatic recovery | `degraded-states.json`, E2E step 9 |
| Backup/restore | exact round trip; a restored clip downloads and decodes | `backup-restore.json` |
| Cold start, 3× | done in Phase 1 | `cold-starts.json` |
| Production rehearsal | HTTPS via Caddy, release-step migrations, first-admin bootstrap, secure cookies, SSE and evidence through the proxy, internal ports closed, dev secrets refused | `production-rehearsal.json` |
| 30-min 3-stream soak | **Passed:** min 2.73 fps, median 3.0, 0 failures, no memory growth. The baseline failed (local AI reviews starved the detector); fixed by capping review threads. | `stream-soak-final-assessment.json`, `stream-soak-baseline-assessment.json` |

Tests (2026-11-06): API 102, video-ingest 47, orchestrator 46, detector 10,
stream-publisher 3, frontend 23. Lint and typecheck are clean. The
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
- **Notifications:** Telegram + webhook outbox (ADR 0013). **Telegram not
  tried with a real bot.**
- **AI review:** scene, verdict, model name and latency; specific failure
  reasons; optional native-Ollama fallback; 384 px clean frames; background
  model loading; shared runner options (ADR 0014).
- **Operations:** `/v1/system/status` with an app-wide degraded banner and
  a Monitoring services panel; `/ready`; backup/restore; Caddy production
  overlay; CUDA and remote detector backends; non-root images.
- **Pages cut:** Safety and Occupancy dashboards counted incident types the
  pipeline never produces; they now redirect to filtered Live Ops.

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

- **Footage:** one supplied clip (a convenience store, licence
  undocumented). Restricted entry, after-hours entry, loitering, unattended
  bag and blocked exit are unit-tested on synthetic tracks only.
- **Owner-dependent:** real phone camera, Telegram delivery, footage for
  office and campus.
- Local CPU AI review misses p95 ≤ 30 s (34 s) when incidents coincide; the hosted model passes.
- `npm audit`: 8 moderate findings in the ESLint dev toolchain; production
  dependencies are clean.
- Notification secrets are unencrypted at rest (never returned by the
  API); expired `auth_sessions` rows are not pruned.
