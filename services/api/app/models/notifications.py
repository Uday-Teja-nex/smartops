from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

CHANNEL_KINDS = ("telegram", "webhook")
DELIVERY_STATES = ("pending", "sent", "dead")


class NotificationChannelModel(Base):
    """A destination plus the rule deciding which incidents reach it.

    `config` holds destination secrets (Telegram bot token, webhook signing
    secret). They are never serialized back to clients.
    """

    __tablename__ = "notification_channels"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # Rule: minimum severity, categories (empty = all), optional local hours.
    min_severity: Mapped[str] = mapped_column(String(16), default="high", nullable=False)
    categories: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    active_hours: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NotificationDeliveryModel(Base):
    """Outbox row, written in the same transaction as the incident."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (UniqueConstraint("incident_id", "channel_id", name="uq_delivery_incident_channel"),)

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False, index=True)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"), nullable=True, index=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
