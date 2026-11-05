from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class AuthSessionModel(Base):
    """One signed-in browser session.

    Access tokens carry the session id (`sid`) and are rejected once the
    session is revoked, so logout takes effect immediately. The refresh token
    itself is never stored: only its SHA-256 digest, plus the digest it
    replaced so that replay of a rotated token revokes the whole session.
    """

    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    refresh_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    previous_refresh_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
