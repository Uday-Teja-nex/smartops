from datetime import UTC, datetime, timedelta
from pathlib import Path as FilePath

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, require_admin, require_supervisor, require_viewer
from app.config import get_settings
from app.db import get_db_session
from app.events import publish_event
from app.ids import new_id
from app.models import BuildingModel, FloorModel, IncidentModel, SourceModel, ZoneModel
from app.schemas import (
    SourceCreateRequest,
    SourceHealthReport,
    SourceResponse,
    SourceUpdateRequest,
)
from app.serializers import serialize_source

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


def _maybe_create_source_health_incident(
    session: Session, source: SourceModel, payload: SourceHealthReport, previous_status: str
) -> None:
    """Rule-based System Health incident when a source starts failing.

    This is explicitly NOT model-driven: it is a deterministic rule on
    adapter health reports, and is labeled as such via modelProvider.
    """
    if payload.status != "failing" or previous_status == "failing":
        return

    open_health_incident = session.scalars(
        select(IncidentModel).where(
            IncidentModel.source_id == source.id,
            IncidentModel.category == "System Health",
            IncidentModel.status.in_(("active", "acknowledged", "assigned", "in_progress")),
        )
    ).first()
    if open_health_incident is not None:
        return

    now = datetime.now(UTC)
    session.add(
        IncidentModel(
            id=new_id("inc"),
            org_id=source.org_id,
            category="System Health",
            subcategory="camera_offline",
            event_type="camera_offline",
            severity="high",
            confidence=1.0,
            status="active",
            building_id=source.building_id,
            floor=source.floor_label,
            zone=source.zone_label,
            source_id=source.id,
            candidate_id=None,
            start_time=now,
            end_time=None,
            sla_due_at=now + timedelta(minutes=120),
            short_summary=f"Video source '{source.name}' is failing health checks",
            detailed_narrative=[
                "The ingestion adapter reported a failing health probe.",
                f"Adapter: {payload.adapter or 'unknown'}.",
                f"Error: {payload.lastError or 'no error message provided'}.",
            ],
            recommended_actions=[
                "Check source power, storage, and network.",
                "Verify the source URI and credentials.",
                "Escalate to facilities IT if unresolved.",
            ],
            review_notes=["Created by rule-based source health monitoring (no model involved)."],
            evidence_thumbnail_url="/evidence-placeholder.svg",
            evidence_clip_url="/restricted",
            evidence_restricted=True,
            assigned_to=None,
            model_provider="rule-engine",
            model_version="source-health-v1",
            detection_summary={},
            created_at=now,
            updated_at=now,
        )
    )


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
    # A paused/disabled source keeps its lifecycle status; health details are
    # still recorded so the UI can show the last probe result.
    if source.enabled and source.status != "paused":
        source.status = payload.status
        _maybe_create_source_health_incident(session, source, payload, previous_status)
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
