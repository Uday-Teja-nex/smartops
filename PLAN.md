# SmartOps plan

Goal: GOAL_PROMPT.md (a live, honest, client-demoable product on the laptop;
cloud-ready). Status as of 2026-11-11. "Verified" means measured on this
laptop, with evidence in `docs/verification/`.

## Phase gates

| Phase | Gate | Status |
|---|---|---|
| 0 Audit | every claim evidenced | Done (`docs/AUDIT.md`) |
| 1 Honest and stable | 3 cold ups; no runtime mocks; offline state | Done (`cold-starts.json`, `phase1-*`) |
| 2 Streaming pipeline | Tier 1 events ≤ 5 s on recorded footage; 30-min 3-stream soak | **Soak passed:** 30 min, 3 streams, 138 samples, min 2.73 fps (median 3.0), no stalls, no memory growth (`stream-soak-final-assessment.json`), after capping local AI review CPU (the baseline failed). Live push 0.3–3.0 s (E2E). Proven on real footage: queue and crowding (store), crowding (mall atrium, office lobby; after switching count rules to raw detections), restricted entry (office, campus). Unattended bag, blocked exit, loitering and after-hours: synthetic tracks only (no licensed footage exists; owner to record). |
| 3 AI layer | ≥ 95 % validated, p95 ≤ 30 s, honest failures | **Passed with the hosted model** (11/11, p95 10.1 s). Local CPU only, four cameras: 12/12 attempted reviews validated (2 skipped by the per-camera interval, reason shown) but p95 64.5 s; with two cameras locally: p95 34.2 s. The laptop CPU cannot meet 30 s locally; a GPU host or hosted model is required. Honest failures verified. |
| 4 Product | tenancy + role tests; a notification on a real phone | **Passed** pending the owner's confirmation of receipt: a real crowding incident was accepted by Telegram for the owner's private chat 2.2 s after the rule fired (`notifications-telegram.json`). Tenancy and role tests pass. Phone-camera onboarding is built but not yet tried with a real phone. |
| 5 Demo-ready | Section C script 5× from reset, screenshots | **Passed on the current stack** (2026-11-11, attempt 8, demo history loaded): 5/5 consecutive runs, 9/9 steps each, 57/58 live clips ready, 0 DB pool errors (`e2e/five-runs-final/`). Attempts 1–7 are archived with their causes and fixes. Screenshots are in `docs/presentation/screens/`. The phone-camera and Telegram steps need the owner. |

## Needs the owner

1. Record unattended-bag, blocked-exit and loitering clips
   (`docs/FOOTAGE_SHOT_LIST.md`); no licensed stock footage exists.
2. Try "Add phone camera" with a phone on the same Wi-Fi (allow TCP 1935).
3. Confirm the Telegram messages arrived on your phone.
4. Local-only AI review latency: smaller models were benchmarked and
   rejected (`review-model-benchmark.json`); meeting p95 ≤ 30 s locally
   needs a GPU host or hosted credit.

## Production rehearsal

Passed 2026-11-06 (`production-rehearsal.json`): HTTPS via Caddy's internal
CA, release-step migrations, first admin via `python -m app.create_admin`,
secure cookies, SSE and evidence through the proxy, closed internal ports,
dev secrets refused. Let's Encrypt on a public domain is not exercised.

## Client-IT items (added to the goal 2026-11-11)

All built and tested: credentials encrypted at rest (`SMARTOPS_SECRETS_KEY`),
user management and own-password change, per-workspace evidence retention
with audited purge, multi-tab sessions with pruning, `/metrics` on the API,
orchestrator and detector with Monitoring backed by them, `pip-audit` clean
and `npm audit` clean for production (dev-only finding documented in
`docs/verification/dependency-audit.md`), and the "How SmartOps handles
data" page linked from the console footer.

## Next engineering steps

1. Validate the remaining Tier 1 rules on real footage once it arrives, and
   tune the zones.
2. Move `SMARTOPS_SECRETS_KEY` into a secrets manager on the cloud host;
   add email invites and SSO when a client asks.
3. Re-run `npm audit` once typescript-eslint ships a stable minimatch fix.
