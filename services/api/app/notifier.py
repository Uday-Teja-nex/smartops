"""Notification sender process: `python -m app.notifier`.

Polls the delivery outbox, sends due rows and records the outcome. Rows are
claimed with SELECT ... FOR UPDATE SKIP LOCKED on PostgreSQL, so several
notifier replicas never double-send. Non-retryable failures, or a sixth
failed attempt, move a row to `dead` with its last error kept for Monitoring.
"""

from __future__ import annotations

import logging
import signal
import time
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.models import IncidentModel, NotificationChannelModel, NotificationDeliveryModel
from app.notifications import MAX_ATTEMPTS, DeliveryError, incident_payload, retry_delay, send

log = logging.getLogger("smartops.notifier")
HEARTBEAT_KEY = "smartops:heartbeat:notifier"
_running = True


def _stop(*_: object) -> None:
    global _running
    _running = False


def process_due(session: Session, client: httpx.Client, limit: int = 20) -> int:
    now = datetime.now(UTC)
    query = (
        select(NotificationDeliveryModel)
        .where(NotificationDeliveryModel.status == "pending", NotificationDeliveryModel.next_attempt_at <= now)
        .order_by(NotificationDeliveryModel.next_attempt_at)
        .limit(limit)
    )
    if engine.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    rows = session.scalars(query).all()
    for row in rows:
        channel = session.get(NotificationChannelModel, row.channel_id)
        incident = session.get(IncidentModel, row.incident_id) if row.incident_id else None
        row.attempts += 1
        if channel is None or incident is None or incident.org_id != row.org_id or channel.org_id != row.org_id:
            row.status, row.last_error = "dead", "Channel or incident no longer exists in this workspace"
            continue
        try:
            send(channel, incident_payload(incident), client)
        except DeliveryError as exc:
            row.last_error = str(exc)[:500]
            if not exc.retryable or row.attempts >= MAX_ATTEMPTS:
                row.status = "dead"
                log.warning("notification dead", extra={"delivery": row.id, "reason": row.last_error})
            else:
                row.next_attempt_at = datetime.now(UTC) + retry_delay(row.attempts)
            continue
        row.status, row.sent_at, row.last_error = "sent", datetime.now(UTC), None
        log.info("notification sent", extra={"delivery": row.id, "channel": channel.kind})
    session.commit()
    return len(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log.info("notifier started")
    from redis import Redis

    from app.config import get_settings
    beat = Redis.from_url(get_settings().redis_url, socket_timeout=2, socket_connect_timeout=2)
    next_purge = 0.0
    with httpx.Client(timeout=10) as client:
        while _running:
            if time.time() >= next_purge:
                # Evidence retention runs hourly in this long-lived process.
                next_purge = time.time() + 3600
                try:
                    from app.retention import purge_expired_evidence, remove_from_storage
                    with SessionLocal() as session:
                        purged = purge_expired_evidence(session, remove_from_storage)
                    if purged:
                        log.info("evidence purged", extra={"items": purged})
                except Exception:  # noqa: BLE001 - retried next hour
                    log.exception("evidence retention run failed")
            try:
                beat.set(HEARTBEAT_KEY, str(time.time()), ex=15)
            except Exception:  # noqa: BLE001 - status pages report the missing heartbeat.
                pass
            try:
                with SessionLocal() as session:
                    handled = process_due(session, client)
            except Exception:  # noqa: BLE001 - keep polling through DB restarts.
                log.exception("notifier cycle failed")
                handled = 0
            if not handled:
                time.sleep(1.0)
    log.info("notifier stopped")


if __name__ == "__main__":
    main()
