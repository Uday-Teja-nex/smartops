"""Short-lived, timestamped observations. They are not historical analytics."""
from datetime import UTC, datetime
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from redis import Redis, RedisError
from sqlalchemy.orm import Session

from app.auth import Principal, require_supervisor, require_viewer
from app.config import get_settings
from app.db import get_db_session
from app.events import publish_event
from app.models import SourceModel
from app.schemas import DetectionBox

router = APIRouter(prefix='/v1/sources', tags=['live'])
cache = Redis.from_url(get_settings().redis_url, decode_responses=True)


class LiveDetection(BaseModel):
    label: str = Field(max_length=80)
    confidence: float = Field(ge=0, le=1)
    bbox: DetectionBox


class LiveTrack(BaseModel):
    track_id: int = Field(ge=1)
    label: str = Field(max_length=80)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)


class LiveObservation(BaseModel):
    sequence: int = Field(ge=1)
    capturedAt: datetime
    width: int = Field(ge=1, le=4096)
    height: int = Field(ge=1, le=4096)
    detections: list[LiveDetection] = Field(default_factory=list, max_length=200)
    tracks: list[LiveTrack] = Field(default_factory=list, max_length=200)
    previewJpeg: str | None = Field(default=None, max_length=500000, pattern=r'^[A-Za-z0-9+/]*={0,2}$')


def source_for(source_id, session, principal):
    source = session.get(SourceModel, source_id)
    if source is None or (principal.kind != 'service' and source.org_id != principal.org_id):
        raise HTTPException(status_code=404, detail='Source not found')
    return source


@router.post('/{source_id}/observations')
def publish_observation(source_id: str, payload: LiveObservation,
                        session: Session = Depends(get_db_session),
                        principal: Principal = Depends(require_supervisor)):
    source = source_for(source_id, session, principal)
    if payload.capturedAt.tzinfo is None:
        raise HTTPException(status_code=422, detail='capturedAt requires a timezone')
    age = (datetime.now(UTC) - payload.capturedAt).total_seconds()
    if age > 5 or age < -2:
        raise HTTPException(status_code=422, detail='Observation timestamp is not current')
    data = payload.model_dump(mode='json')
    data.update(sourceId=source.id, orgId=source.org_id)
    try:
        cache.set(f'smartops:live:{source.id}', json.dumps(data), ex=10)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail='Live cache unavailable') from exc
    publish_event('observation', data)
    return {'sequence': payload.sequence}


@router.get('/{source_id}/observations')
def get_observation(source_id: str, session: Session = Depends(get_db_session),
                    principal: Principal = Depends(require_viewer)):
    source_for(source_id, session, principal)
    try:
        raw = cache.get(f'smartops:live:{source_id}')
    except RedisError as exc:
        raise HTTPException(status_code=503, detail='Live cache unavailable') from exc
    if raw is None:
        raise HTTPException(status_code=404, detail='No recent observation')
    return json.loads(raw)
