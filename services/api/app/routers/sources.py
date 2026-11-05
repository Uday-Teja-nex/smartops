import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from pathlib import Path as FilePath

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, require_admin, require_supervisor, require_viewer
from app.config import get_settings
from app.tenancy import get_tenant_session as get_db_session
from app.events import publish_event
from app.ids import new_id
from app.models import BuildingModel, FloorModel, IncidentModel, SourceModel, ZoneModel
from app.schemas import (
    SourceCreateRequest,
    SourceHealthReport,
    SourceResponse,
    SourceUpdateRequest,
)
from app.serializers import serialize_incident, serialize_source

router = APIRouter(prefix="/v1", tags=["sources"], dependencies=[Depends(require_viewer)])
settings = get_settings()


def _get_source_or_404(source_id: str, session: Session) -> SourceModel:
    source = session.get(SourceModel, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return source


def _resolve_topology(
    session: Session,
    building_id: str,
    floor_id: str | None,
    zone_id: str | None,
    floor_label: str | None,
    zone_label: str | None,
) -> tuple[str | None, str | None, str, str]:
    """Validate structured floor/zone links and derive display labels."""
    building = session.get(BuildingModel, building_id)
    if building is None:
        raise HTTPException(status_code=404, detail="Building not found")

    resolved_floor_label = floor_label or ""
    resolved_zone_label = zone_label or ""

    if floor_id:
        floor = session.get(FloorModel, floor_id)
        if floor is None or floor.building_id != building_id:
            raise HTTPException(status_code=400, detail="Floor does not belong to building")
        resolved_floor_label = resolved_floor_label or floor.level
    if zone_id:
        zone = session.get(ZoneModel, zone_id)
        if zone is None:
            raise HTTPException(status_code=400, detail="Zone not found")
        if floor_id and zone.floor_id != floor_id:
            raise HTTPException(status_code=400, detail="Zone does not belong to floor")
        resolved_zone_label = resolved_zone_label or zone.name

    if not resolved_floor_label:
        raise HTTPException(status_code=422, detail="floor or floorId is required")
    if not resolved_zone_label:
        raise HTTPException(status_code=422, detail="zone or zoneId is required")

    return floor_id, zone_id, resolved_floor_label, resolved_zone_label


@router.get("/sources", response_model=list[SourceResponse])
def list_sources(
    session: Session = Depends(get_db_session),
    building_id: str | None = Query(default=None, alias="buildingId"),
    status: str | None = Query(default=None),
    source_type: str | None = Query(default=None, alias="sourceType"),
    enabled: bool | None = Query(default=None),
    floor: str | None = Query(default=None),
    zone: str | None = Query(default=None),
) -> list[SourceResponse]:
    query = select(SourceModel).order_by(SourceModel.name)
    if building_id:
        query = query.where(SourceModel.building_id == building_id)
    if status:
        query = query.where(SourceModel.status == status)
    if source_type:
        query = query.where(SourceModel.source_type == source_type)
    if enabled is not None:
        query = query.where(SourceModel.enabled == enabled)
    if floor:
        query = query.where(SourceModel.floor_label == floor)
    if zone:
        query = query.where(SourceModel.zone_label == zone)
    sources = session.scalars(query).all()
    return [serialize_source(source) for source in sources]


@router.get("/sources/{source_id}", response_model=SourceResponse)
def get_source(source_id: str, session: Session = Depends(get_db_session)) -> SourceResponse:
    return serialize_source(_get_source_or_404(source_id, session))


@router.post("/sources", response_model=SourceResponse, status_code=201)
def create_source(
    payload: SourceCreateRequest,
    session: Session = Depends(get_db_session),
    _: Principal = Depends(require_supervisor),
) -> SourceResponse:
    floor_id, zone_id, floor_label, zone_label = _resolve_topology(
        session, payload.buildingId, payload.floorId, payload.zoneId, payload.floor, payload.zone
    )
    building = session.get(BuildingModel, payload.buildingId)
    now = datetime.now(UTC)
    source = SourceModel(
        id=new_id("src"),
        org_id=building.org_id,
        building_id=payload.buildingId,
        floor_id=floor_id,
        zone_id=zone_id,
        floor_label=floor_label,
        zone_label=zone_label,
        name=payload.name,
        source_type=payload.sourceType,
        source_uri=payload.sourceUri,
        input_format=payload.inputFormat,
        credentials_ref=payload.credentialsRef,
        enabled=payload.enabled,
        status="offline",
        health={},
        tags=payload.tags,
        position_notes=payload.positionNotes,
        detection_config=payload.detectionConfig,
        created_at=now,
        updated_at=now,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    response = serialize_source(source)
    publish_event("source", response.model_dump(mode="json"))
    return response


@router.patch("/sources/{source_id}", response_model=SourceResponse)
def update_source(
    source_id: str,
    payload: SourceUpdateRequest,
    session: Session = Depends(get_db_session),
    _: Principal = Depends(require_supervisor),
) -> SourceResponse:
    source = _get_source_or_404(source_id, session)

    if payload.buildingId or payload.floorId or payload.zoneId or payload.floor or payload.zone:
        building_id = payload.buildingId or source.building_id
        floor_id, zone_id, floor_label, zone_label = _resolve_topology(
            session,
            building_id,
            payload.floorId if payload.floorId is not None else source.floor_id,
            payload.zoneId if payload.zoneId is not None else source.zone_id,
            payload.floor if payload.floor is not None else source.floor_label,
            payload.zone if payload.zone is not None else source.zone_label,
        )
        source.building_id = building_id
        source.floor_id = floor_id
        source.zone_id = zone_id
        source.floor_label = floor_label
        source.zone_label = zone_label

    if payload.name is not None:
        source.name = payload.name
    if payload.sourceType is not None:
        source.source_type = payload.sourceType
    if payload.sourceUri is not None:
        source.source_uri = payload.sourceUri
    if payload.inputFormat is not None:
        source.input_format = payload.inputFormat
    if payload.credentialsRef is not None:
        source.credentials_ref = payload.credentialsRef
    if payload.enabled is not None:
        source.enabled = payload.enabled
    if payload.status is not None:
        source.status = payload.status
    if payload.tags is not None:
        source.tags = payload.tags
    if payload.positionNotes is not None:
        source.position_notes = payload.positionNotes
    if payload.detectionConfig is not None:
        source.detection_config = payload.detectionConfig

    source.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(source)
    response = serialize_source(source)
    publish_event("source", response.model_dump(mode="json"))
    return response


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(
    source_id: str,
    session: Session = Depends(get_db_session),
    _: Principal = Depends(require_admin),
) -> None:
    source = _get_source_or_404(source_id, session)
    session.delete(source)
    session.commit()


def _set_lifecycle(
    session: Session, source: SourceModel, *, enabled: bool | None, status: str
) -> SourceModel:
    if enabled is not None:
        source.enabled = enabled
    source.status = status
    source.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(source)
    publish_event("source", serialize_source(source).model_dump(mode="json"))
    return source


@router.post("/sources/{source_id}/pause", response_model=SourceResponse)
def pause_source(
    source_id: str,
    session: Session = Depends(get_db_session),
    _: Principal = Depends(require_supervisor),
) -> SourceResponse:
    source = _get_source_or_404(source_id, session)
    return serialize_source(_set_lifecycle(session, source, enabled=None, status="paused"))


@router.post("/sources/{source_id}/resume", response_model=SourceResponse)
def resume_source(
    source_id: str,
    session: Session = Depends(get_db_session),
    _: Principal = Depends(require_supervisor),
) -> SourceResponse:
    source = _get_source_or_404(source_id, session)
    return serialize_source(_set_lifecycle(session, source, enabled=True, status="offline"))


@router.post("/sources/{source_id}/disable", response_model=SourceResponse)
def disable_source(
    source_id: str,
    session: Session = Depends(get_db_session),
    _: Principal = Depends(require_supervisor),
) -> SourceResponse:
    source = _get_source_or_404(source_id, session)
    return serialize_source(_set_lifecycle(session, source, enabled=False, status="offline"))


HEALTH_DESCRIPTIONS = {
    "camera_offline": "No fresh frames are available",
    "camera_low_light": "Sustained low image luminance",
    "camera_obscured": "Possible covered lens or uniform view; inspect the camera",
    "camera_frozen": "Possible frozen video or static scene; frames remain nearly unchanged",
}


def _maybe_create_source_health_incident(
    session: Session, source: SourceModel, payload: SourceHealthReport, previous_status: str
) -> list[IncidentModel]:
    if payload.status not in {"failing", "offline"} or payload.details.get('warmingUp'):
        return []
    reported = payload.details.get("issues", [])
    kinds = [kind for kind in HEALTH_DESCRIPTIONS if kind in reported]
    if not kinds:
        kinds = ["camera_offline"]
    previous_issues = (source.health or {}).get("issues", [])
    incidents = []
    for kind in kinds:
        if previous_status == payload.status and kind in previous_issues:
            continue
        existing = session.scalars(select(IncidentModel).where(
            IncidentModel.source_id == source.id,
            IncidentModel.event_type == kind,
            IncidentModel.status.in_(("active", "acknowledged", "assigned", "in_progress")),
        )).first()
        if existing is not None:
            continue
        now = datetime.now(UTC)
        incident = IncidentModel(
            id=new_id("inc"), org_id=source.org_id, category="System Health",
            subcategory=kind, event_type=kind, severity="high" if kind == "camera_offline" else "medium",
            confidence=1.0, status="active", building_id=source.building_id,
            floor=source.floor_label, zone=source.zone_label, source_id=source.id,
            start_time=now, sla_due_at=now + timedelta(minutes=120),
            short_summary=f"{source.name}: {HEALTH_DESCRIPTIONS[kind]}",
            detailed_narrative=[], recommended_actions=[],
            review_notes=["Measured source-health rule; image quality does not establish tampering or its cause."],
            evidence_thumbnail_url="", evidence_clip_url="", evidence_restricted=True,
            model_provider="rule-engine", model_version="source-health-v2",
            detection_summary={"adapter": payload.adapter, "error": payload.lastError, **payload.details},
            created_at=now, updated_at=now,
        )
        session.add(incident)
        incidents.append(incident)
    return incidents


@router.post("/sources/{source_id}/health", response_model=SourceResponse)
def report_source_health(
    source_id: str,
    payload: SourceHealthReport,
    session: Session = Depends(get_db_session),
    _: Principal = Depends(require_supervisor),
) -> SourceResponse:
    """Ingestion services report adapter health here."""
    source = _get_source_or_404(source_id, session)
    now = datetime.now(UTC)
    previous_status = source.status
    health_incidents = []
    # A paused/disabled source keeps its lifecycle status; health details are
    # still recorded so the UI can show the last probe result.
    if source.enabled and source.status != "paused":
        source.status = payload.status
        health_incidents = _maybe_create_source_health_incident(session, source, payload, previous_status)
    source.health = {
        "lastSeen": now.isoformat(),
        "lastError": payload.lastError,
        "latencyMs": payload.latencyMs,
        "adapter": payload.adapter,
        "reportedStatus": payload.status,
        **payload.details,
    }
    source.updated_at = now
    session.commit()
    session.refresh(source)
    response = serialize_source(source)
    publish_event("source", response.model_dump(mode="json"))
    for incident in health_incidents:
        publish_event("incident", serialize_incident(incident).model_dump(mode="json"))
    return response


@router.get("/sources/{source_id}/clip")
def get_source_clip(
    source_id: str, session: Session = Depends(get_db_session)
) -> FileResponse:
    """Serve the raw local MP4 for file-based sources (local dev only)."""
    source = _get_source_or_404(source_id, session)
    if source.source_type != "file":
        raise HTTPException(status_code=404, detail="No local clip is available for this source")

    source_root = FilePath(settings.source_root).resolve()
    source_path = FilePath(source.source_uri).resolve()
    if source_root not in source_path.parents:
        raise HTTPException(status_code=403, detail="Clip is outside the allowed source root")
    if not source_path.exists() or source_path.suffix.lower() != ".mp4":
        raise HTTPException(status_code=404, detail="Clip not found")

    return FileResponse(source_path, media_type="video/mp4", filename=source_path.name)


class PhoneCameraRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    buildingId: str
    floorId: str | None = None
    zoneId: str | None = None
    floor: str | None = None
    zone: str | None = None


@router.post("/sources/phone", status_code=201)
def create_phone_camera(
    payload: PhoneCameraRequest,
    session: Session = Depends(get_db_session),
    principal: Principal = Depends(require_supervisor),
) -> dict:
    """Register a phone as a live camera and return where it should publish.

    The phone publishes RTMP to mediamtx on the laptop's LAN address with a
    publish-only credential that is limited to phone-* paths; nothing on the
    LAN can read streams. The processor picks the camera up like any other
    RTSP source within a few seconds.
    """
    if principal.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")
    path = f"phone-{secrets.token_hex(3)}"
    created = create_source(SourceCreateRequest(
        name=payload.name, buildingId=payload.buildingId, floorId=payload.floorId, zoneId=payload.zoneId,
        floor=payload.floor, zone=payload.zone, sourceType="rtsp",
        sourceUri=f"rtsp://{settings.mediamtx_rtsp_host}:8554/{path}", inputFormat="h264",
        tags=["phone"], positionNotes="Phone camera publishing over RTMP from the local network.",
    ), session, principal)
    host = settings.ingest_public_host
    query = urlencode({"user": settings.phone_publish_user, "pass": settings.phone_publish_password})
    return {
        "source": created.model_dump(mode="json"),
        "publish": {
            "rtmpUrl": f"rtmp://{host}:1935/{path}?{query}",
            "server": f"rtmp://{host}:1935/{path}",
            "streamKey": f"?{query}",
            "path": path,
            "lanHostConfigured": host not in {"localhost", "127.0.0.1"},
        },
    }
