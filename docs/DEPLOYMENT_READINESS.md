# Deployment readiness

Last updated 2026-11-11. The laptop demo and a cloud deployment use the same
compose files. `docker-compose.prod.yml` adds Caddy, production settings and
closes every port except HTTPS and WebRTC media.

## What production mode enforces (tested)

- **Startup refuses** default or short JWT/internal secrets, default object
  storage secrets, a missing `SMARTOPS_SECRETS_KEY`, the demo account as
  platform admin, demo seeding, wildcard CORS and a non-Secure refresh cookie
  (`services/api/tests/test_config.py`).
- **Stored credentials:** notification channel secrets (Telegram bot tokens,
  webhook signing secrets) are encrypted at rest with Fernet under
  `SMARTOPS_SECRETS_KEY` and never returned by the API. Losing the key makes
  them unreadable; the API then says which setting to fix.
- **Users:** admins invite (one-time temporary password), change roles,
  deactivate and reset passwords in Settings; everyone changes their own
  password under Account. Deactivation and resets sign that person out
  everywhere. No one can deactivate or demote themselves.
- **Sessions:** 15-minute access tokens bound to a server-side session;
  rotating HttpOnly SameSite=Strict refresh cookie; logout revokes access,
  refresh and SSE tickets immediately; replay of a rotated refresh token
  revokes the session (ADR 0012). A 30 s grace lets several tabs refresh at
  once. Sessions ended more than 7 days ago are pruned.
- **Evidence retention:** per workspace (default 30 days, 1-3650, admin
  only, on the "How SmartOps handles data" page). Clips and snapshots older
  than that are deleted hourly by the notifier; each incident's timeline
  records the deletion.
- **Passwords:** argon2id; old PBKDF2 hashes upgrade on login.
- **Login throttling:** 5 per account and 30 per address per minute, shared
  in Redis (ADR 0011).
- **Request bodies:** capped at 2 MiB by default before routing.
- **Tenancy:** every user query is scoped to the user's workspace in one place
  (`app/tenancy.py`); cross-workspace reads return 404 (tests in
  `test_workspace_boundaries.py`, `test_notifications.py`). The internal
  pipeline principal works across workspaces, but every write takes its
  workspace from the camera it references.
- **Evidence:** URLs are issued only to signed-in humans with the right
  role, are short-lived, and every issuance is audited.
- **Containers:** every SmartOps service runs as a non-root user.
- **Migrations:** a release step (`python -m app.migrate`); API replicas
  refuse to start against an outdated schema.
- **Health:** `/health` on every service; API `/ready` checks PostgreSQL and
  Redis.
- **Metrics:** Prometheus `/metrics` on the API, orchestrator and detector.
  The Monitoring page shows detector and AI-review p50/p95 and outcome shares
  from them (percentages only: those services are shared by every workspace).
- **Database connections:** authentication uses its own short session, so
  open live-update (SSE) streams never hold a pooled connection.
- **Dependencies:** `pip-audit` clean for every Python service; `npm audit`
  clean for production dependencies (`docs/verification/dependency-audit.md`).

## Move to a Linux GPU VM

1. **VM:** Ubuntu 24.04, an NVIDIA GPU with at least 16 GB of VRAM for 7B
   vision models (8 GB is enough for `qwen2.5vl:3b`), 8 vCPU, 32 GB RAM,
   100 GB disk. Install the NVIDIA driver, Docker Engine and the NVIDIA
   Container Toolkit.
2. **DNS and firewall:** point `ops.example.com` at the VM. Open 80/tcp,
   443/tcp, 443/udp and 8189/udp (WebRTC media). Add the domain to
   `webrtcAdditionalHosts` in `mediamtx.yml`.
3. **Secrets:** copy `.env.production.example` to `.env.production` and fill
   it. Generate each secret with
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`, and
   `SMARTOPS_SECRETS_KEY` with
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
   Back that key up with the database: without it, stored channel secrets
   cannot be read.
4. **Models:** either run Ollama in Docker on the GPU (`--profile
   docker-ollama`, `SMARTOPS_OLLAMA_HOST=http://ollama:11434`, add `gpus: all`
   to the `ollama` service), or point `SMARTOPS_MODEL_PROVIDER=openai-compatible`
   at a vLLM server. On a 16 GB GPU `qwen2.5vl:7b` is the next quality step.
5. **Detector on GPU:** build with
   `--build-arg TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121`, set
   `SMARTOPS_DETECTOR_BACKEND=ultralytics-cuda` and give the detector the GPU.
   Alternatively keep the detector on CPU and use `remote` to reach a GPU box.
6. **Release:**

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production build
   docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production run --rm api python -m app.migrate
   docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.production up -d
   ```

7. **First workspace:** set `SMARTOPS_SEED_DEMO_DATA=true` for one start to
   create the demo workspaces and admin accounts, change the admin passwords,
   then set it back to `false`.

## Known gaps before a paying production deployment

- `SMARTOPS_SECRETS_KEY` is a single key in the environment. For a regulated
  client, keep it in a secrets manager and plan rotation (re-encrypt channels
  with the new key).
- mediamtx publish/read is unauthenticated on its internal network. Before
  exposing RTSP/RTMP ingest publicly, add per-camera credentials.
- Invites hand over a temporary password; there is no email delivery or SSO
  (SAML/OIDC) yet.
- ESLint dev tooling carries a moderate `minimatch` advisory until
  typescript-eslint ships a stable fix (dev-only; see the audit note).
- Single-node: PostgreSQL, Redis and MinIO run as single containers on the
  VM. Use managed services for real high availability.
- Backups: `demo.ps1 backup`/`restore` are tested on the laptop. On a server,
  schedule `pg_dump` plus object-store replication.
