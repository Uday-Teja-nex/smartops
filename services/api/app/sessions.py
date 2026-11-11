"""Server-side sign-in sessions with rotating, revocable refresh tokens.

The refresh token is an opaque 256-bit random value delivered only as an
HttpOnly cookie scoped to /v1/auth. The database stores its SHA-256 digest.
Each refresh rotates it; presenting the previous (already rotated) token is
treated as theft and revokes the session.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ids import new_id
from app.models import AuthSessionModel, UserModel

REFRESH_COOKIE = "smartops_refresh"
REFRESH_COOKIE_PATH = "/v1/auth"
# A rotated refresh token is still accepted this long after its rotation, for
# concurrent refreshes from tabs sharing one cookie; later replay revokes.
REUSE_GRACE = timedelta(seconds=30)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    # SQLite returns naive datetimes; PostgreSQL returns aware ones.
    return value if value.tzinfo else value.replace(tzinfo=UTC)


PRUNE_AFTER = timedelta(days=7)


def prune_sessions(session: Session, user_id: str, now: datetime) -> int:
    """Delete this user's sessions that ended (revoked or expired) over a week ago."""
    from sqlalchemy import delete, or_
    cutoff = now - PRUNE_AFTER
    result = session.execute(delete(AuthSessionModel).where(
        AuthSessionModel.user_id == user_id,
        or_(AuthSessionModel.revoked_at < cutoff, AuthSessionModel.expires_at < cutoff)))
    return result.rowcount or 0


def open_session(session: Session, user: UserModel) -> tuple[AuthSessionModel, str]:
    now = datetime.now(UTC)
    prune_sessions(session, user.id, now)
    token = secrets.token_urlsafe(32)
    record = AuthSessionModel(
        id=new_id("ses"),
        org_id=user.org_id,
        user_id=user.id,
        refresh_hash=_digest(token),
        created_at=now,
        last_used_at=now,
        expires_at=now + timedelta(hours=get_settings().refresh_ttl_hours),
    )
    session.add(record)
    session.flush()
    return record, token


class RefreshRejected(Exception):
    pass


def rotate_session(session: Session, token: str) -> tuple[AuthSessionModel, UserModel, str]:
    digest = _digest(token)
    now = datetime.now(UTC)
    record = session.scalars(select(AuthSessionModel).where(AuthSessionModel.refresh_hash == digest)).first()
    if record is None:
        replayed = session.scalars(
            select(AuthSessionModel).where(AuthSessionModel.previous_refresh_hash == digest)
        ).first()
        if replayed is None or replayed.revoked_at is not None:
            raise RefreshRejected("Session expired. Sign in again.")
        if now - _aware(replayed.last_used_at) <= REUSE_GRACE:
            # Two tabs of one browser refreshing together: the second sends the
            # token the first just rotated. Treat it as the same refresh.
            record = replayed
        else:
            replayed.revoked_at = now
            replayed.revoked_reason = "refresh_reuse"
            session.commit()
            raise RefreshRejected("Session expired. Sign in again.")
    if record.revoked_at is not None or _aware(record.expires_at) <= now:
        raise RefreshRejected("Session expired. Sign in again.")
    user = session.get(UserModel, record.user_id)
    if user is None or not user.active or user.org_id != record.org_id:
        record.revoked_at = now
        record.revoked_reason = "account_unavailable"
        session.commit()
        raise RefreshRejected("Account unavailable")
    new_token = secrets.token_urlsafe(32)
    if record.refresh_hash == digest:
        # Normal rotation: remember the token being replaced. (A grace-window
        # reuse keeps the earlier previous hash, so the window cannot slide.)
        record.previous_refresh_hash = digest
        record.last_used_at = now
    record.refresh_hash = _digest(new_token)
    session.flush()
    return record, user, new_token


def revoke_by_refresh(session: Session, token: str, reason: str = "logout") -> bool:
    record = session.scalars(
        select(AuthSessionModel).where(AuthSessionModel.refresh_hash == _digest(token))
    ).first()
    return _revoke(record, reason)


def revoke_by_id(session: Session, session_id: str, user_id: str, reason: str = "logout") -> bool:
    record = session.get(AuthSessionModel, session_id)
    if record is None or record.user_id != user_id:
        return False
    return _revoke(record, reason)


def _revoke(record: AuthSessionModel | None, reason: str) -> bool:
    if record is None or record.revoked_at is not None:
        return False
    record.revoked_at = datetime.now(UTC)
    record.revoked_reason = reason
    return True


def session_is_active(session: Session, session_id: str, user_id: str) -> bool:
    record = session.get(AuthSessionModel, session_id)
    return (
        record is not None
        and record.user_id == user_id
        and record.revoked_at is None
        and _aware(record.expires_at) > datetime.now(UTC)
    )
