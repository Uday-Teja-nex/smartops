# Notification outbox

Date: 2026-11-06

Notifications are per workspace. A channel is a destination (Telegram bot or
generic webhook) plus its rule: minimum severity, optional category list
(empty means all), and optional active hours in an IANA timezone. Windows
that cross midnight, such as 22:00–06:00, are supported.

When the API first inserts an incident, it writes one `notification_deliveries`
row per matching channel in the same database transaction. An incident
therefore can't exist without its deliveries, and a failed insert leaves no
orphan deliveries. Re-submissions of an existing incident (pipeline retries,
AI enrichment) never notify again, and a unique constraint on
(incident, channel) backs this up. The decision uses the rule as it stood when
the incident was created; editing a channel later doesn't re-evaluate history.

A separate `notifier` process, built from the API image (about 55 MiB),
polls due rows every second. On PostgreSQL it claims them with
`FOR UPDATE SKIP LOCKED`, so extra replicas can't double-send. HTTP 429, 5xx
and network errors retry with exponential backoff (5 s doubling, capped at
5 min). Other 4xx responses, a missing configuration, or a sixth failed
attempt mark the row `dead` and keep the last error. Settings shows sent,
retrying and failed counts per channel.

Telegram delivery is a text message: severity, human-readable event type,
summary, zone/floor, which component detected it (`rule-engine` or a model
name) and a console link. Webhooks receive `{"event": "incident.created",
"incident": {...}}` and, when a secret is configured, an
`X-SmartOps-Signature: sha256=<hex HMAC of the raw body>` header. Production
requires https webhook URLs.

Bot tokens and webhook secrets are stored in the channel's JSON config in
PostgreSQL and never returned by the API. Responses show only a masked
destination and which keys are set. Error messages never include the
Telegram request URL, because it contains the token. Encrypting the secrets
at rest with a deployment key is left for the cloud move; on the laptop the
database and the .env file are equally sensitive.

Settings → Notifications replaces the old per-organization "email digest" and
"webhook on critical" checkboxes and the category threshold inputs. Nothing
read those values, so showing them as working features was misleading.
