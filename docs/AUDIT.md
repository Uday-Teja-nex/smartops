# SmartOps audit — 2026-10-22

Phase 0 audit completed on 2026-10-24 with the limitations below. This document
distinguishes observed facts from hypotheses; no product acceptance gate has passed.

## Verified baseline

- Initial `docker compose ps -a`: all ten SmartOps containers stopped. Other
  project's Supabase services were running and were not modified.
- WSL configuration is 4 GB memory / 2 GB swap. Docker reports 3.821 GiB.
- Started existing postgres, redis, minio, API, detector and frontend containers.
  API is running with restart count zero on this warm start. This does not
  reproduce or disprove the reported cold-start crash.
- Idle memory snapshot: API 82.87 MiB, detector 270.2 MiB, frontend 261 MiB,
  Redis 7.188 MiB, MinIO 92.12 MiB, Postgres 36.33 MiB (750 MiB total).
  Ingest, worker and orchestrator are stopped; this is NOT a full-stack or
  loaded-inference measurement. Raw snapshot: `verification/phase0-memory.txt`.
- Existing frontend container command is `npm run dev -- --hostname 0.0.0.0`.
  However the current Dockerfile's final stage is production; the existing
  image differs from source. Rebuild and measure before drawing conclusions.
- Database SQL aggregation found four incidents, all `fallen_object`,
  `human_review`, confidence 0.35. `graph.py:_mark_human_review` explicitly
  fabricates that type, confidence, observations and actions on model failure.
- Historical Docker Ollama log shows HTTP 500 after 67 seconds and
  `llama-server process has terminated: signal: killed`. Saved in
  `verification/phase0-ollama-failures.txt`.
- Native Ollama was started. `/api/tags` lists only `qwen3-coder:latest` and
  `llama3:latest`, contrary to the supplied audit. Downloads of the required
  `qwen2.5vl:3b` and `llama3.2:3b` have been started. GPU benchmark is pending.
  `nvidia-smi` reports RTX 3050 Ti family GPU with 4096 MiB VRAM visible.
- Runtime mock imports exist in providers, Overview and Housekeeping.
  Providers also turn failed writes into local successful-looking state changes.
  `analytics.ts` contains the invented pantry-delivery root cause.
- RTSP adapter returns unsupported/offline and raises AdapterNotImplemented.
  Worker accepts local paths; compose samples three frames per window and
  caps file discovery at twelve windows. Model/worker timeouts are 480/540 s.
- SSE has an additional concrete routing defect: `/incidents/{incident_id}`
  is registered before the pipeline router's `/incidents/stream`. Historical
  request logs show `/v1/incidents/stream` returning 404 repeatedly.
- Evidence URL access uses unscoped `session.get`; role restrictions and
  access auditing are absent. Browser playback failure has not yet been
  independently reproduced. Detail reload depends on the entire sources
  array, so source updates can repeatedly fetch the incident and evidence URL.
- Alembic calls `fileConfig` without `disable_existing_loggers=False`.
  Suppressed startup logging is a supported hypothesis, not yet a reproduced
  root cause of the original startup failure.
- SLA formatting has no days unit; large hour counts follow directly from
  `slaCountdown`. Direct-session restore code already restores from JWT before
  the network request; the reported hang still needs browser reproduction.
- Lint and TypeScript check emitted no errors. Vitest: 7 passed outside
  sandbox (sandbox run failed on a temporary cache-file rename permission).
  Python service baseline tests are still running separately.

## Keep / rewrite / delete

| Component | Decision and reason |
|---|---|
| API | Keep models, migrations, CRUD and audit foundations; rewrite tenant/auth boundaries, startup, SSE routing and evidence authorization. |
| Postgres / Redis / MinIO | Keep; verify readiness, durability, resource usage and recovery. |
| video-ingest | Replace bounded file-window scheduling with continuous stream adapters. |
| worker | Retain useful evidence encoding/storage; replace window workflow with tracking, rules and incident-first persistence. |
| detector | Keep backend interface and YOLO; extend backend choices and tracking integration. |
| orchestrator | Keep provider boundary and schema validation; remove fabricated fallback and move to asynchronous enrichment. |
| Docker Ollama | Optional profile; native GPU default after benchmark. |
| Overview | Rewrite with stored metrics and honest offline/empty states. |
| Live Ops | Keep incident workflow; repair SSE, failures and labels. |
| Incident detail | Keep workflow; fix playback, reload dependencies, SLA and provenance. |
| Sources | Extend with real streams, zone editor and phone onboarding. |
| Occupancy | Replace with stored zone counts after processor exists. |
| Safety / Housekeeping | Merge or remove unsupported metrics; retain only real incident filtering if useful. |
| Reports | Keep real aggregation utilities; remove invented narrative; implement exports. |
| Monitoring | Extend to actual service/stream telemetry. |
| Settings | Replace cosmetic preferences with enforced workspace/auth/notifier settings. |
| Login | Keep presentation; harden token lifecycle and offline recovery. |
| Mock data / old presentation claims | Remove from runtime and rewrite documentation. |

## Follow-up evidence and limitations

- Python baselines passed: API 21, orchestrator 11, worker 7. See
  `verification/phase0-checks.txt` for timings and browser observations.
- Authenticated evidence GET returned HTTP 206, video/mp4. Browser decoded
  the 20.01-second clip and advanced to 4.48 seconds after Play. Direct incident
  navigation succeeded. Playback/ORB and session-hang reports were not reproduced.
- Screenshots: `verification/phase0-overview.png` and `phase0-incident.png`.
- Full non-model service snapshot is in `phase0-full-stack-memory.txt`.
  Memory changed with WSL reclamation; the earlier loaded development frontend
  reached 973.2 MiB. These snapshots are not soak-test evidence.
- Native Qwen benchmark failed: native server log on 2026-10-22 21:44:39 IST
  reports 3.2 GiB model weights plus 6.7 GiB CPU compute graph, 9.9 GiB total,
  load failure and HTTP 500 after 180 seconds. No successful inference latency
  or GPU utilization claim is possible. Both requested native model downloads
  completed. Native service was stopped when work resumed on October 24.
- A preceding localhost benchmark was ambiguous because Docker Ollama had
  claimed the same port. Docker Ollama is now stopped; benchmark script uses
  explicit IPv4. Future setup must prevent this port conflict.
- Fresh Postgres database `smartops_audit` migration and seeding succeeded on
  October 24 (`verification/phase0-fresh-database.txt`). Original crash-loop
  cause remains unproven; logging must be repaired before cold-start testing.
- On October 24 the frontend was stopped with exit 137; other non-model
  services remained running. Exit 137 alone does not prove an OOM kill.
- Supplied audit detection total is stale: SQL counted 656 person detections.

Phase 1 will remove fabrication and repair startup observability and SSE.
Phase 3 must benchmark smaller inference batch/model configurations before
the AI latency and success-rate requirements can be considered achievable.
