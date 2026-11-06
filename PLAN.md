# SmartOps plan

Goal: GOAL_PROMPT.md (a live, honest, client-demoable product on the laptop;
cloud-ready). Status as of 2026-11-06. "Verified" means measured on this
laptop, with evidence in `docs/verification/`.

## Phase gates

| Phase | Gate | Status |
|---|---|---|
| 0 Audit | every claim evidenced | Done (`docs/AUDIT.md`) |
| 1 Honest and stable | 3 cold ups; no runtime mocks; offline state | Done (`cold-starts.json`, `phase1-*`) |
| 2 Streaming pipeline | Tier 1 events ≤ 5 s on recorded footage; 30-min 3-stream soak | **Soak passed:** 30 min, 3 streams, 138 samples, min 2.73 fps (median 3.0), no stalls, no memory growth (`stream-soak-final-assessment.json`), after capping local AI review CPU (the baseline failed). Live push 0.3–3.0 s (E2E). Queue and crowding are proven on real footage; the other Tier 1 rules only on synthetic tracks (no footage yet). |
| 3 AI layer | ≥ 95 % validated, p95 ≤ 30 s, honest failures | **Passed with the hosted model** (11/11, p95 10.1 s). Local CPU only: 10/10 validated but p95 38.3 s. Honest failures verified. |
| 4 Product | tenancy + role tests; a notification on a real phone | **Partly.** Tenancy and role tests pass (API and E2E). Webhook verified end to end. Telegram on a real phone needs the owner's bot token. |
| 5 Demo-ready | Section C script 5× from reset, screenshots | **Passed** for everything automatable: 5/5 consecutive runs, 9/9 steps each (`e2e/five-runs/`); screenshots in `docs/presentation/screens/`. The phone-camera and Telegram steps need the owner. |

## Needs the owner

1. Footage for each Tier 1 event and for the office and campus workspaces
   (shot list: `docs/FOOTAGE_SHOT_LIST.md`; record provenance in
   `sample-data/README.md`).
2. A Telegram bot token and chat ID (Settings → Notifications → Add channel).
3. A phone on the same Wi-Fi to try "Add phone camera". Allow inbound TCP
   1935 when Windows Firewall asks.
4. Optional: approval to pull a smaller local vision model, or OpenRouter
   credit (the free tier allows 50 requests a day), to bring local review
   p95 under 30 s.

## Next engineering steps

1. Production rehearsal: the prod overlay with `SMARTOPS_DOMAIN=localhost`,
   `SMARTOPS_TLS=internal` (separate project name, so the demo stack is
   unaffected).
2. Validate the remaining Tier 1 rules on real footage once it arrives, and
   tune the zones.
3. Encrypt notification secrets at rest; prune expired sessions.
