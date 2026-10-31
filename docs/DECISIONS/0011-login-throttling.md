# Shared login throttling

Date: 2026-11-01

Login attempts are limited in Redis before password hashing: five attempts per
normalized account and thirty per client address in a fixed 60-second window.
Successful and failed attempts both count. One Lua operation increments both
counters and assigns expirations atomically across API processes. A denied
request does not extend the window. Keys use HMAC digests rather than raw email
addresses or IPs. No passwords enter the counters.

Redis failure blocks new sign-ins with 503 and Retry-After, rather than silently
removing brute-force protection. Existing bearer sessions remain usable. The
client receives 429 and the remaining window when throttled. Temporary account
throttling can be triggered by an attacker; the short window bounds this cost.

The address comes from the ASGI request client, not an application-level read
of X-Forwarded-For. Production proxy configuration must trust only the actual
proxy's forwarding headers; clients behind an unconfigured proxy can share the
address limit. This deployment configuration remains to be verified.

Local tests verify rejection before password verification, fail-closed behavior,
and normalized private keys. Live Redis expiry/concurrency verification remains
pending along with Docker recovery; mock tests do not prove Lua execution.
