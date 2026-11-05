from datetime import UTC, datetime
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, require_admin, require_supervisor
from app.config import get_settings
from app.ids import new_id
from app.models import NotificationChannelModel, NotificationDeliveryModel
from app.notifications import (
    CHANNEL_KINDS_CONFIG,
    ChannelConfigError,
    DeliveryError,
    send,
    validate_active_hours,
)
from app.tenancy import get_tenant_session

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])

Severity = Literal["low", "medium", "high", "critical"]


class ActiveHours(BaseModel):
    start: str
    end: str
    timezone: str = "UTC"


class ChannelInput(BaseModel):
    kind: Literal["telegram", "webhook"]
    name: str = Field(min_length=1, max_length=120)
    enabled: bool = True
    minSeverity: Severity = "high"
    categories: list[str] = Field(default_factory=list, max_length=12)
    activeHours: ActiveHours | None = None
    # telegram: botToken, chatId. webhook: url, optional secret.
    config: dict[str, str] = Field(default_factory=dict)


class ChannelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None
    minSeverity: Severity | None = None
    categories: list[str] | None = Field(default=None, max_length=12)
    activeHours: ActiveHours | None = None
    clearActiveHours: bool = False
    # Only keys present are replaced; secrets are never echoed back.
    config: dict[str, str] | None = None


class ChannelResponse(BaseModel):
    id: str
    kind: str
    name: str
    enabled: bool
    minSeverity: str
    categories: list[str]
    activeHours: dict[str, Any] | None
    destination: str
    configured: list[str]
    createdAt: datetime
    updatedAt: datetime


class DeliveryResponse(BaseModel):
    id: str
    incidentId: str | None
    channelId: str
    status: str
    attempts: int
    lastError: str | None
    createdAt: datetime
    sentAt: datetime | None


def _mask(value: str) -> str:
    return value if len(value) <= 4 else "…" + value[-4:]


def _destination(channel: NotificationChannelModel) -> str:
    config = channel.config or {}
    if channel.kind == "telegram":
        return f"Telegram chat {_mask(str(config.get('chatId', '')))}" if config.get("chatId") else "Telegram (no chat)"
    url = str(config.get("url", ""))
    try:
        return httpx.URL(url).host or "Webhook (no URL)"
    except Exception:  # noqa: BLE001
        return "Webhook (invalid URL)"


def _serialize(channel: NotificationChannelModel) -> ChannelResponse:
    return ChannelResponse(
        id=channel.id, kind=channel.kind, name=channel.name, enabled=channel.enabled,
        minSeverity=channel.min_severity, categories=list(channel.categories or []),
        activeHours=channel.active_hours, destination=_destination(channel),
        configured=sorted(key for key, value in (channel.config or {}).items() if value),
        createdAt=channel.created_at, updatedAt=channel.updated_at,
    )


def _validated_config(kind: str, config: dict[str, str]) -> dict[str, str]:
    allowed = CHANNEL_KINDS_CONFIG[kind]
    unknown = set(config) - allowed["required"] - allowed["optional"]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown {kind} settings: {', '.join(sorted(unknown))}")
    missing = [key for key in sorted(allowed["required"]) if not str(config.get(key, "")).strip()]
    if missing:
        raise HTTPException(status_code=422, detail=f"{kind} channel requires {', '.join(missing)}")
    clean = {key: str(value).strip() for key, value in config.items() if str(value).strip()}
    if kind == "webhook":
        url = clean["url"]
        production = get_settings().environment.strip().lower() == "production"
        if not url.startswith("https://") and (production or not url.startswith("http://")):
            raise HTTPException(status_code=422, detail="Webhook URL must use https://")
    return clean


def _hours(hours: ActiveHours | None) -> dict[str, Any] | None:
    try:
        return validate_active_hours(hours.model_dump() if hours else None)
    except ChannelConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _get(session: Session, channel_id: str) -> NotificationChannelModel:
    channel = session.scalars(select(NotificationChannelModel).where(NotificationChannelModel.id == channel_id)).first()
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return channel


@router.get("/channels", response_model=list[ChannelResponse])
def list_channels(session: Session = Depends(get_tenant_session),
                  principal: Principal = Depends(require_supervisor)) -> list[ChannelResponse]:
    rows = session.scalars(select(NotificationChannelModel).order_by(NotificationChannelModel.created_at)).all()
    return [_serialize(row) for row in rows]


@router.post("/channels", response_model=ChannelResponse, status_code=201)
def create_channel(payload: ChannelInput, session: Session = Depends(get_tenant_session),
                   principal: Principal = Depends(require_admin)) -> ChannelResponse:
    now = datetime.now(UTC)
    channel = NotificationChannelModel(
        id=new_id("chn"), org_id=principal.org_id, kind=payload.kind, name=payload.name.strip(),
        enabled=payload.enabled, config=_validated_config(payload.kind, payload.config),
        min_severity=payload.minSeverity, categories=payload.categories,
        active_hours=_hours(payload.activeHours), created_at=now, updated_at=now,
    )
    session.add(channel)
    session.commit()
    return _serialize(channel)


@router.patch("/channels/{channel_id}", response_model=ChannelResponse)
def update_channel(channel_id: str, payload: ChannelUpdate, session: Session = Depends(get_tenant_session),
                   principal: Principal = Depends(require_admin)) -> ChannelResponse:
    channel = _get(session, channel_id)
    if payload.name is not None:
        channel.name = payload.name.strip()
    if payload.enabled is not None:
        channel.enabled = payload.enabled
    if payload.minSeverity is not None:
        channel.min_severity = payload.minSeverity
    if payload.categories is not None:
        channel.categories = payload.categories
    if payload.clearActiveHours:
        channel.active_hours = None
    elif payload.activeHours is not None:
        channel.active_hours = _hours(payload.activeHours)
    if payload.config is not None:
        channel.config = _validated_config(channel.kind, {**(channel.config or {}), **payload.config})
    channel.updated_at = datetime.now(UTC)
    session.commit()
    return _serialize(channel)


@router.delete("/channels/{channel_id}", status_code=204)
def delete_channel(channel_id: str, session: Session = Depends(get_tenant_session),
                   principal: Principal = Depends(require_admin)) -> Response:
    channel = _get(session, channel_id)
    for delivery in session.scalars(
        select(NotificationDeliveryModel).where(NotificationDeliveryModel.channel_id == channel.id)
    ).all():
        session.delete(delivery)
    session.delete(channel)
    session.commit()
    return Response(status_code=204)


@router.post("/channels/{channel_id}/test")
def test_channel(channel_id: str, session: Session = Depends(get_tenant_session),
                 principal: Principal = Depends(require_admin)) -> dict[str, Any]:
    channel = _get(session, channel_id)
    console = get_settings().console_public_url.rstrip("/")
    payload = {
        "id": "test", "url": console, "type": "test", "typeLabel": "Test notification",
        "category": "System Health", "severity": "low", "status": "test",
        "summary": f"SmartOps test message for channel '{channel.name}'. No incident was created.",
        "zone": None, "floor": None, "detectedBy": "manual test", "confidence": None,
    }
    try:
        with httpx.Client(timeout=10) as client:
            send(channel, payload, client)
    except DeliveryError as exc:
        return {"delivered": False, "error": str(exc)}
    return {"delivered": True, "error": None}


@router.get("/deliveries", response_model=list[DeliveryResponse])
def list_deliveries(session: Session = Depends(get_tenant_session),
                    principal: Principal = Depends(require_supervisor)) -> list[DeliveryResponse]:
    rows = session.scalars(
        select(NotificationDeliveryModel).order_by(NotificationDeliveryModel.created_at.desc()).limit(100)
    ).all()
    return [DeliveryResponse(id=row.id, incidentId=row.incident_id, channelId=row.channel_id, status=row.status,
                             attempts=row.attempts, lastError=row.last_error, createdAt=row.created_at,
                             sentAt=row.sent_at) for row in rows]
