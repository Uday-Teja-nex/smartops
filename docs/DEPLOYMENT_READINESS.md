# Deployment readiness

Last updated 2026-11-06. The laptop demo and a cloud deployment use the same
compose files. `docker-compose.prod.yml` adds Caddy, production settings and
closes every port except HTTPS and WebRTC media.

## What production mode enforces (tested)

- **Startup refuses** default or short JWT/internal secrets, default object
  storage secrets, demo seeding, wildcard CORS and a non-Secure refresh cookie
  (`services/api/tests/test_config.py`).
- **Sessions:** 15-minute access tokens bound to a server-side session;
  rotating HttpOnly SameSite=Strict refresh cookie; logout revokes access,
  refresh and SSE tickets immediately; replay of a rotated refresh token
  revokes the session (ADR 0012).
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
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
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

- Notification secrets (Telegram bot tokens, webhook secrets) are stored in
  the database unencrypted, though never returned by the API. Add envelope
  encryption with a deployment key.
- mediamtx publish/read is unauthenticated on its internal network. Before
  exposing RTSP/RTMP ingest publicly, add per-camera credentials.
- No user invitation or password-change UI yet; accounts come from the seed
  or the database.
- Expired `auth_sessions` rows are not pruned.
- Single-node: PostgreSQL, Redis and MinIO run as single containers on the
  VM. Use managed services for real high availability.
- Backups: `demo.ps1 backup`/`restore` are tested on the laptop. On a server,
  schedule `pg_dump` plus object-store replication.
