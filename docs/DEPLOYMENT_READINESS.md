# Deployment Readiness

What must change before real customers/buildings run on SmartOps. Local
development intentionally uses relaxed defaults; every item below is
structural (the code has a single place to change it).

## Blocking (must do)

| Area | Current state | Required |
|---|---|---|
| Secrets | Dev defaults in compose (`SMARTOPS_JWT_SECRET`, `SMARTOPS_INTERNAL_TOKEN`, DB/MinIO passwords) | Secrets manager / env injection; rotate; fail startup on dev defaults outside development |
| Password hashing | PBKDF2-SHA256 (stdlib, format is self-describing) | Migrate to argon2id/bcrypt with rehash-on-login; add password reset + invitation flows |
| Auth hardening | Long-lived JWT (12h), no refresh, no revocation | Short-lived access + refresh tokens, logout revocation list, rate-limited login |
| RBAC / tenancy | Roles enforced per endpoint; single seeded org; org_id present on all rows but not yet filtered per request | Derive org from principal and filter every query by it; per-building scoping for security/ehs roles |
| Evidence privacy | Presigned URLs for any authenticated viewer | Role/incident-scoped evidence grants + access audit log (single choke point: `GET /v1/evidence/{id}/url`) |
| TLS / ingress | Plain HTTP everywhere | Reverse proxy (Caddy/Traefik/nginx) with TLS; SSE-friendly (no buffering) |
| Real camera inputs | MP4 adapter only | Implement + soak-test RTSP (then ONVIF/WebRTC) against real hardware; credentials via `credentials_ref` → secrets store |
| Retention | Nothing expires | Retention policies for evidence objects, detections, resolved incidents; MinIO lifecycle rules |
| Backups | Manual commands documented | Scheduled pg_dump + MinIO mirror, restore drills |

## Strongly recommended

- **Scaling**: multiple workers (safe: BRPOP + idempotent incident upsert),
  detector replicas or GPU/ONNX backend, per-source rate limits.
- **Monitoring**: scrape `/metrics`, alert on dead-letter queue depth,
  `failing` sources, VLM failure rate (`human_review` ratio), SSE client counts.
- **Model serving**: dedicated inference host or hosted API provider;
  the 4GB laptop profile is not a deployment profile.
- **Security review**: dependency scanning, container hardening (non-root
  users, read-only rootfs), CORS tightening, request size limits.
- **Migrations**: run `alembic upgrade` as a release step (not app startup)
  in multi-replica deployments.

## Nice to have

- SSO/OIDC instead of local passwords.
- Notification delivery (email/webhook) wired to the stored org preferences.
- Kubernetes manifests/Helm (compose file maps 1:1 to Deployments/Services).
- Vector store only if/when semantic search over incidents becomes a feature.
