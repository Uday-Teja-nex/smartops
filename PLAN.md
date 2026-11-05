# SmartOps plan

Goal: GOAL_PROMPT.md (a live, honest, client-demoable product on the laptop;
cloud-ready). Status as of 2026-11-06. "Verified" means measured on this
laptop, with evidence in `docs/verification/`.

## Phase gates

| Phase | Gate | Status |
|---|---|---|
| 0 Audit | every claim evidenced | Done (`docs/AUDIT.md`) |
| 1 Honest and stable | 3 cold ups; no runtime mocks; offline state | Done (`cold-starts.json`, `phase1-*`) |
| 2 Streaming pipeline | Tier 1 events ≤ 5 s on recorded footage; 30-min 3-stream soak | **Partly.** Queue and crowding fire live on the mall clip and persist about 50 ms after the rule triggers. The other Tier 1 rules are unit-tested on synthetic tracks but have no footage. The soak has never passed (about 3 fps per stream; dips below 2 fps). |
| 3 AI layer | ≥ 95 % validated, p95 ≤ 30 s, honest failures | **Partly.** Honest failures and the local fallback are verified; the live latency measurement is in `enrichment-live.json`. |
| 4 Product | tenancy + role tests; a notification on a real phone | **Partly.** Tenancy, roles, sessions and the notifier are tested; a webhook was delivered end to end (1.0 s). Telegram needs the owner's bot token. Workspace-creation UI and phone onboarding are not built. |
| 5 Demo-ready | Section C script 5× from reset, screenshots | **Not started:** needs Playwright E2E, footage for every Tier 1 event, the phone flow. |

## Done in the 2026-11-06 session

- Docker Desktop crash loop fixed (stale socket files); `demo.ps1 fix-docker`.
- `demo.ps1`: preflight, up (28 s), reset (6 s), status, backup, restore.
- Three seeded workspaces on one streaming code path, with a publisher
  manifest.
- Revocable sessions, rotating refresh cookies, argon2id, non-root images.
- Telegram and webhook notifier with a transactional outbox and retries.
- Rule cooldowns and readable rule incidents.
- AI review with scene, verdict and model; specific failure reasons;
  native-Ollama fallback.
- Production overlay behind Caddy, release-step migrations, `/ready`, CUDA
  and remote detector backends.

## Next, in order

1. Footage for each Tier 1 event (owner; shot list in
   `docs/FOOTAGE_SHOT_LIST.md`).
2. Phone camera onboarding: a source wizard showing the RTMP/RTSP publish URL
   and a QR code, ≤ 60 s.
3. Workspace creation UI for prospects (name, accent, buildings, cameras).
4. Playwright E2E for the Section C script against the compose stack.
5. Monitoring page: per-camera fps/lag, detector and VLM latency, queue
   depth, delivery failures (most data is already exposed).
6. Stream soak at ≥ 2 fps per stream for 30 minutes (try 2 fps target with
   detector at 512 px, or fewer streams on CPU).
7. Cut or merge the Safety, Housekeeping and Occupancy pages into views
   backed by real data.
8. Production rehearsal: run the prod overlay locally with
   `SMARTOPS_DOMAIN=localhost`, `SMARTOPS_TLS=internal`.
