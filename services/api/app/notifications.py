"""Incident notifications: rule matching, outbox enqueue and channel senders.

Matching happens when an incident is first persisted, inside the same
transaction, so a crash can never create an incident without its deliveries
(or deliveries without the incident). Sending happens later in the notifier
process (app.notifier) with retries and a dead-letter state.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ids import new_id
from app.models import IncidentModel, NotificationChannelModel, NotificationDeliveryModel

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
MAX_ATTEMPTS = 6
CHANNEL_KINDS_CONFIG = {
    "telegram": {"required": {"botToken", "chatId"}, "optional": set()},
    "webhook": {"required": {"url"}, "optional": {"secret"}},
}
_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ChannelConfigError(ValueError):
    pass


def validate_active_hours(hours: dict[str, Any] | None) -> dict[str, Any] | None:
    if not hours:
        return None
    start, end, zone = hours.get("start"), hours.get("end"), hours.get("timezone", "UTC")
    if not (isinstance(start, str) and _HHMM.match(start) and isinstance(end, str) and _HHMM.match(end)):
        raise ChannelConfigError("Active hours need start and end as HH:MM")
    if start == end:
        raise ChannelConfigError("Active hours start and end must differ (omit them for all day)")
    try:
        ZoneInfo(str(zone))
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ChannelConfigError(f"Unknown timezone {zone!r}") from exc
    return {"start": start, "end": end, "timezone": str(zone)}


def within_hours(hours: dict[str, Any] | None, at: datetime) -> bool:
    if not hours:
        return True
    local = at.astimezone(ZoneInfo(hours["timezone"])).time()
    start, end = time.fromisoformat(hours["start"]), time.fromisoformat(hours["end"])
    if start < end:
        return start <= local < end
    return local >= start or local < end  # window crosses midnight


def channel_matches(channel: NotificationChannelModel, incident: IncidentModel, at: datetime) -> bool:
    if not channel.enabled:
        return False
    if SEVERITY_RANK.get(incident.severity, 0) < SEVERITY_RANK.get(channel.min_severity, 2):
        return False
    if channel.categories and incident.category not in channel.categories:
        return False
    return within_hours(channel.active_hours, at)


def enqueue_for_incident(session: Session, incident: IncidentModel) -> int:
    """Add outbox rows for every matching channel. Call before commit."""
    now = datetime.now(UTC)
    channels = session.scalars(
        select(NotificationChannelModel).where(
            NotificationChannelModel.org_id == incident.org_id,
            NotificationChannelModel.enabled.is_(True),
        )
    ).all()
    count = 0
    for channel in channels:
        if channel_matches(channel, incident, now):
            session.add(NotificationDeliveryModel(
                id=new_id("ntf"), org_id=incident.org_id, incident_id=incident.id, channel_id=channel.id,
                status="pending", attempts=0, next_attempt_at=now, created_at=now,
            ))
            count += 1
    return count


def retry_delay(attempts: int) -> timedelta:
    return timedelta(seconds=min(5 * 2 ** max(attempts - 1, 0), 300))


# ---------------------------------------------------------------------------
# Message content
# ---------------------------------------------------------------------------

def humanize(value: str | None) -> str:
    if not value:
        return ""
    return value.replace("_", " ").replace("-", " ").strip().capitalize()


def incident_payload(incident: IncidentModel) -> dict[str, Any]:
    console = get_settings().console_public_url.rstrip("/")
    return {
        "id": incident.id,
        "url": f"{console}/incidents/{incident.id}",
        "type": incident.event_type,
        "typeLabel": humanize(incident.event_type),
        "category": incident.category,
        "severity": incident.severity,
        "status": incident.status,
        "summary": incident.short_summary,
        "buildingId": incident.building_id,
        "floor": incident.floor,
        "zone": incident.zone,
        "sourceId": incident.source_id,
        "startTime": incident.start_time.isoformat() if incident.start_time else None,
        "detectedBy": incident.model_provider,
        "confidence": incident.confidence,
    }


def telegram_text(payload: dict[str, Any]) -> str:
    where = " · ".join(part for part in (payload.get("zone"), payload.get("floor")) if part)
    lines = [
        f"[{payload['severity'].upper()}] {payload['typeLabel']}",
        payload.get("summary") or "",
        f"Where: {where}" if where else "",
        f"Detected by: {payload.get('detectedBy') or 'unknown'}",
        payload["url"],
    ]
    return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------
# Senders. Each raises DeliveryError; `retryable` decides retry vs dead.
# ---------------------------------------------------------------------------

class DeliveryError(Exception):
    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


def _classify(response: httpx.Response, destination: str) -> None:
    if response.is_success:
        return
    retryable = response.status_code == 429 or response.status_code >= 500
    raise DeliveryError(f"{destination} returned HTTP {response.status_code}", retryable=retryable)


def send_telegram(config: dict[str, Any], payload: dict[str, Any], client: httpx.Client) -> None:
    token, chat_id = config.get("botToken"), config.get("chatId")
    if not token or not chat_id:
        raise DeliveryError("Telegram channel is missing botToken or chatId", retryable=False)
    try:
        response = client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": telegram_text(payload), "disable_web_page_preview": True},
        )
    except httpx.HTTPError as exc:
        # Never include the request URL: it contains the bot token.
        raise DeliveryError(f"Telegram unreachable ({type(exc).__name__})", retryable=True) from None
    _classify(response, "Telegram")


def webhook_signature(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def send_webhook(config: dict[str, Any], payload: dict[str, Any], client: httpx.Client) -> None:
    url = config.get("url")
    if not url or not str(url).startswith(("https://", "http://")):
        raise DeliveryError("Webhook channel has no valid URL", retryable=False)
    body = json.dumps({"event": "incident.created", "incident": payload}, separators=(",", ":")).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "SmartOps-Notifier/1"}
    if config.get("secret"):
        headers["X-SmartOps-Signature"] = webhook_signature(str(config["secret"]), body)
    try:
        response = client.post(str(url), content=body, headers=headers)
    except httpx.HTTPError as exc:
        raise DeliveryError(f"Webhook unreachable ({type(exc).__name__})", retryable=True) from None
    _classify(response, "Webhook")


SENDERS = {"telegram": send_telegram, "webhook": send_webhook}


def send(channel: NotificationChannelModel, payload: dict[str, Any], client: httpx.Client) -> None:
    sender = SENDERS.get(channel.kind)
    if sender is None:
        raise DeliveryError(f"Unsupported channel kind {channel.kind}", retryable=False)
    from app.secret_box import open_
    sender(open_(channel.config), payload, client)
