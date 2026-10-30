import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from redis import Redis
from redis import asyncio as aioredis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, require_viewer
from app.config import get_settings
from app.db import engine
from app.events import EVENTS_CHANNEL
from app.models import IncidentModel, SourceModel
from app.serializers import serialize_incident, serialize_source

# require_viewer accepts the JWT as a `token` query parameter, which is how
# the SSE stream authenticates (EventSource cannot set headers).
router = APIRouter(prefix="/v1", tags=["pipeline"], dependencies=[Depends(require_viewer)])
settings = get_settings()
redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


@router.get("/pipeline/status")
def pipeline_status() -> dict[str, object]:
    status_keys = list(redis_client.scan_iter("smartops:candidate_status:*", count=100))
    statuses: list[dict[str, object]] = []
    for key in status_keys[:50]:
        raw = redis_client.get(key)
        if not raw:
            continue
        try:
            status = json.loads(raw)
        except json.JSONDecodeError:
            status = {"candidateId": key.rsplit(":", 1)[-1], "state": "unparseable"}
        statuses.append(status)

    statuses.sort(key=lambda item: str(item.get("updatedAt", "")), reverse=True)
    return {
        "queue": settings.candidate_queue,
        "queued": redis_client.llen(settings.candidate_queue),
        "deadLetter": redis_client.llen(settings.dead_letter_queue),
        "recentStatuses": statuses,
    }


def _snapshot_payload(org_id: str) -> str:
    with Session(engine) as session:
        incidents = session.scalars(
            select(IncidentModel).where(IncidentModel.org_id == org_id).order_by(IncidentModel.start_time.desc()).limit(200)
        ).all()
        sources = session.scalars(select(SourceModel).where(SourceModel.org_id == org_id).order_by(SourceModel.name)).all()
        return json.dumps(
            {
                "incidents": [
                    serialize_incident(incident).model_dump(mode="json")
                    for incident in incidents
                ],
                "sources": [
                    serialize_source(source).model_dump(mode="json") for source in sources
                ],
            }
        )


@router.get("/incidents/stream")
async def stream_events(principal: Principal = Depends(require_viewer)) -> StreamingResponse:
    """SSE stream: one initial `snapshot`, then granular Redis pub/sub events.

    Event types:
      - snapshot: {incidents: [...], sources: [...]}
      - incident: one incident record (created or updated)
      - source:   one source record (health/lifecycle change)
    Heartbeat comments are sent while idle so proxies keep the socket open.
    """

    async def event_generator():
        yield f"event: snapshot\ndata: {_snapshot_payload(principal.org_id)}\n\n"

        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        pubsub = client.pubsub()
        await pubsub.subscribe(EVENTS_CHANNEL)
        try:
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=15.0
                )
                if message is None:
                    yield ": heartbeat\n\n"
                    continue
                try:
                    body = json.loads(message["data"])
                    kind = body.get("kind", "incident")
                    if (kind == "observation" and principal.kind != "service"
                            and body.get("data", {}).get("orgId") != principal.org_id):
                        continue
                    if kind in {'incident', 'source'}:
                        model = IncidentModel if kind == 'incident' else SourceModel
                        with Session(engine) as session:
                            owner = session.scalar(select(model.org_id).where(model.id == body.get('data', {}).get('id')))
                        if owner != principal.org_id:
                            continue
                    elif kind != 'observation':
                        continue
                    data = json.dumps(body.get("data", {}))
                except (json.JSONDecodeError, TypeError):
                    continue
                yield f"event: {kind}\ndata: {data}\n\n"
        finally:
            await pubsub.unsubscribe(EVENTS_CHANNEL)
            await client.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
