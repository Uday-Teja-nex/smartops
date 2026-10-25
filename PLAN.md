# SmartOps execution plan

Updated 2026-10-25. The acceptance specification is GOAL_PROMPT.md. Earlier
claims of feature completion were contradicted by the audit and are withdrawn.

## Phase 0 — audit

Audit committed as 0003037. See docs/AUDIT.md and docs/verification/.
Native Qwen inference did not succeed; first-boot crash and playback failure
were not reproduced. These are recorded limitations, not completed fixes.

## Phase 1 — honest and stable (gate passed)

- [x] Regression tests reproduce fabricated failure incidents, SSE route shadowing,
  and missing startup traceback logging.
- [x] Remove failure-generated incidents and canned model narratives/actions.
- [x] Register static SSE route first; preserve logging through migrations.
- [x] Remove runtime mock imports and failed-write local success mutations.
- [x] Replace template AI briefing with clearly computed stored-data summary.
- [x] Build non-root production frontend; bound API requests and fix offline states.
- [x] Stabilize evidence loading and verify browser playback after rebuilding.
- [x] Remove legacy aliases and stale docs.
- [x] Gate: three cold starts (24.00 / 23.49 / 23.95 s), no runtime mock imports, API-stop UI verification.

## Phase 2 — continuous streams

- [x] MediaMTX and one looping MP4 publisher, real reconnecting RTSP adapter.
- [ ] Continuous detection/tracking, polygon zones, schedules and all Tier 1 rules.
- [x] Incident-first persistence, bounded pre/post clips, snapshots and durable delivery.
- [x] Timestamped sampled camera preview with matching real boxes and zone overlays.
- [ ] Full-rate live playback with real detection/zone overlays.
- [x] Footage shot list supplied; local engineering clip provenance recorded.
- [ ] Obtain event footage with commercial-demo permission.
- [ ] Gate: measured <=5-second alerts and 30-minute three-stream soak.

## Phase 3 — AI enrichment

- [ ] Native Ollama warm-up and bounded asynchronous validated enrichment.
- [ ] Benchmark smaller batches/models; default Qwen could not load in audit.
- [ ] OpenAI-compatible and hosted providers; CPU/GPU/remote detector backends.
- [ ] Gate: >=95% validated output, p95 <=30 seconds, explicit failure states.

## Phase 4 — product

- [ ] Central tenant enforcement and cross-org 404 tests.
- [ ] Workspaces, branding, topology and zone/rule editor.
- [ ] Telegram/webhook notification delivery with workspace policy.
- [ ] Real reports, PDF/CSV exports and phone camera onboarding.
- [ ] Argon2id, short access tokens, revocable refresh, rate limits, stream tickets,
  production-secret validation, request limits and audited evidence authorization.
- [ ] Gate: role/tenant tests plus real-phone notification.

## Phase 5 — demo and operations

- [ ] Three client workspaces and pipeline-generated licensed-footage history.
- [ ] demo.ps1 up/preflight/reset with measured timing targets.
- [ ] Full Section C Playwright E2E, five reset runs and screenshots.
- [ ] Fault injection/recovery, backup/restore, metrics and production Caddy run.
- [ ] Responsive polish, honest docs and ten-minute presentation/recovery script.
- [ ] All CI and quality gates green.

Commit each phase; no push or PR. Work sequentially in verified slices. Do not
mark the goal complete while any GOAL_PROMPT.md requirement lacks evidence.
