# Revocable sessions and argon2id

Date: 2026-11-06

Access tokens are HS256 JWTs that live 15 minutes (configurable 1–60). Each
carries `sid`, the id of a row in `auth_sessions`. The API already loads the
user on every request, so it also checks that the session exists, belongs to
the user, is unexpired and is not revoked. Logout therefore takes effect
immediately, not after the access token expires. The same check applies to
30-second SSE stream tickets, which now carry `sid` too, so an open live
stream ends at its next one-minute reconnect after logout.

The refresh token is 256 random bits sent only as an HttpOnly,
SameSite=Strict cookie with Path=/v1/auth. JavaScript can't read it, and the
browser sends it only to the login, refresh and logout routes. The database
stores its SHA-256 digest. Every refresh rotates it and remembers the previous
digest. If someone presents an already rotated token, the session is
revoked: either an attacker or the legitimate browser used a copy. Refresh
also revokes the session when the account has been disabled. Production
startup refuses `SMARTOPS_REFRESH_COOKIE_SECURE=false`.

The console keeps the short-lived access token in localStorage, as before, and
treats it as disposable. On any 401 it makes one refresh call (single-flight,
because two parallel refreshes would look like replay) and retries once. Only
an explicit 401 from refresh signs the user out. A network failure keeps the
session, so an API restart mid-demo shows the offline state instead of the
sign-in page.

Why not keep the access token only in memory? A reload would then always need
a refresh round-trip before the first paint. The 15-minute lifetime plus
server-side revocation bound the XSS exposure enough for this deployment.

Passwords use argon2id with the argon2-cffi defaults (RFC 9106 low-memory
profile). Existing PBKDF2 hashes still verify and are re-hashed on the next
successful login, so no forced password reset is needed.

Not done: listing or revoking other active sessions from the UI. There is no
pruning of expired session rows yet. At demo scale that is a few rows per
sign-in.
