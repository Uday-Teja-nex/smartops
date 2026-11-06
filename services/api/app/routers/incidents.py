from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.auth import Principal, require_human_operator, require_supervisor, require_viewer
from app.tenancy import get_tenant_session as get_db_session
from app.events import publish_event
from app.notifications import enqueue_for_incident
from app.ids import new_id
from app.models import (
    DetectionModel,
    EvidenceItemModel,
    IncidentCommentModel,
    IncidentEventModel,
    IncidentModel,
    SourceModel,
)
from app.models.incidents import INCIDENT_STATUSES
from app.schemas import (
    EventRecordResponse,
    IncidentAssignRequest,
    IncidentCommentCreateRequest,
    IncidentCommentResponse,
    IncidentCreateRequest,
    IncidentDetailResponse,
    IncidentStatusUpdateRequest,
)
from app.serializers import (
    serialize_incident,
    serialize_incident_comment,
    serialize_incident_detail,
)

router = APIRouter(prefix="/v1", tags=["incidents"], dependencies=[Depends(require_viewer)])

# Default SLA windows per severity, applied when the orchestrator does not
# supply an explicit slaDueAt.
SEVERITY_SLA_MINUTES = {
    "critical": 15,
    "high": 60,
    "medium": 240,
    "low": 1440,
}


def _actor_of(principal: Principal) -> str:
    """Audit attribution string derived from the authenticated principal."""
    if principal.kind == "service":
        return "pipeline"
    return f"{principal.name} ({principal.email})"


def get_incident_or_404(incident_id: str, session: Session) -> IncidentModel:
    incident = session.get(IncidentModel, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


def record_incident_event(
    session: Session,
    incident: IncidentModel,
    *,
    actor: str,
    action: str,
    from_status: str | None = None,
    to_status: str | None = None,
    note: str | None = None,
) -> None:
    session.add(
        IncidentEventModel(
            id=new_id("evt"),
            incident_id=incident.id,
            actor=actor,
            action=action,
            from_status=from_status,
            to_status=to_status,
            note=note,
            created_at=datetime.now(UTC),
        )
    )


def default_sla_due(severity: str, start_time: datetime) -> datetime:
    minutes = SEVERITY_SLA_MINUTES.get(severity, SEVERITY_SLA_MINUTES["medium"])
    return start_time + timedelta(minutes=minutes)


@router.get("/incidents", response_model=list[EventRecordResponse])
def list_incidents(
    session: Session = Depends(get_db_session),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    building_id: str | None = Query(default=None, alias="buildingId"),
    source_id: str | None = Query(default=None, alias="sourceId"),
    floor: str | None = Query(default=None),
    zone: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[EventRecordResponse]:
    query = select(IncidentModel).order_by(IncidentModel.start_time.desc()).limit(limit)
    if status:
        query = query.where(IncidentModel.status == status)
    if category:
        query = query.where(IncidentModel.category == category)
    if severity:
        query = query.where(IncidentModel.severity == severity)
    if building_id:
        query = query.where(IncidentModel.building_id == building_id)
    if source_id:
        query = query.where(IncidentModel.source_id == source_id)
    if floor:
        query = query.where(IncidentModel.floor == floor)
    if zone:
        query = query.where(IncidentModel.zone == zone)
    incidents = session.scalars(query).all()
    return [serialize_incident(incident) for incident in incidents]


@router.get("/incidents/{incident_id}", response_model=IncidentDetailResponse)
def get_incident_detail(
    incident_id: str = Path(...),
    session: Session = Depends(get_db_session),
) -> IncidentDetailResponse:
    incident = session.scalars(
        select(IncidentModel)
        .where(IncidentModel.id == incident_id)
        .options(
            selectinload(IncidentModel.events),
            selectinload(IncidentModel.comments),
            selectinload(IncidentModel.evidence_items),
        )
    ).first()
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    detections: list[DetectionModel] = []
    if incident.candidate_id:
        detections = list(
            session.scalars(
                select(DetectionModel)
                .where(DetectionModel.candidate_id == incident.candidate_id)
                .where(DetectionModel.source_id == incident.source_id)
                .order_by(DetectionModel.frame_ts, DetectionModel.frame_index)
            ).all()
        )

    # Evidence uploaded by the worker links via candidate_id (it exists
    # before the incident row does), so match on either key.
    evidence_conditions = [EvidenceItemModel.incident_id == incident.id]
    if incident.candidate_id:
        evidence_conditions.append(EvidenceItemModel.candidate_id == incident.candidate_id)
    evidence_items = list(
        session.scalars(
            select(EvidenceItemModel)
            .where(or_(*evidence_conditions))
            .where(EvidenceItemModel.source_id == incident.source_id)
            .order_by(EvidenceItemModel.created_at)
        ).all()
    )
    return serialize_incident_detail(incident, detections, evidence_items)


@router.post("/incidents", response_model=EventRecordResponse, status_code=201)
def create_incident(
    payload: IncidentCreateRequest,
    session: Session = Depends(get_db_session),
    principal: Principal = Depends(require_supervisor),
) -> EventRecordResponse:
    actor = _actor_of(principal)
    source_id = payload.sourceId
    if not source_id:
        raise HTTPException(status_code=422, detail="sourceId is required")
    source = session.get(SourceModel, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if payload.buildingId != source.building_id:
        raise HTTPException(status_code=422, detail='Incident building must match its source')

    now = datetime.now(UTC)
    incident_id = payload.id or new_id("inc")
    existing = session.get(IncidentModel, incident_id)

    if existing is not None and existing.org_id != source.org_id:
        # Never reveal or modify another workspace's incident, even for the
        # cross-workspace pipeline principal.
        raise HTTPException(status_code=404, detail='Incident not found')
    if existing is not None:
        if existing.source_id != source_id or existing.candidate_id != payload.candidateId:
            raise HTTPException(status_code=409, detail='Incident ID belongs to a different source or candidate')
        # Idempotent re-submission from the pipeline updates the draft fields
        # but never rolls back operator lifecycle state.
        existing.category = payload.category
        existing.subcategory = payload.subcategory
        existing.event_type = payload.type
        existing.severity = payload.severity
        existing.confidence = payload.confidence
        existing.building_id = payload.buildingId
        existing.floor = payload.floor
        existing.zone = payload.zone
        existing.short_summary = payload.shortSummary
        existing.detailed_narrative = payload.detailedNarrative
        existing.recommended_actions = payload.recommendedActions
        existing.review_notes = payload.reviewNotes
        existing.evidence_thumbnail_url = payload.evidence.thumbnailUrl
        existing.evidence_clip_url = payload.evidence.clipUrl
        existing.evidence_restricted = payload.evidence.restricted
        existing.model_provider = payload.modelProvider
        existing.model_version = payload.modelVersion
        existing.detection_summary = payload.detectionSummary
        existing.updated_at = now
        record_incident_event(
            session, existing, actor=actor, action="pipeline_update", note="Incident draft re-submitted"
        )
        session.commit()
        session.refresh(existing)
        response = serialize_incident(existing)
        publish_event("incident", response.model_dump(mode="json"))
        return response

    incident = IncidentModel(
        id=incident_id,
        org_id=source.org_id,
        category=payload.category,
        subcategory=payload.subcategory,
        event_type=payload.type,
        severity=payload.severity,
        confidence=payload.confidence,
        status=payload.status,
        building_id=payload.buildingId,
        floor=payload.floor,
        zone=payload.zone,
        source_id=source_id,
        candidate_id=payload.candidateId,
        start_time=payload.startTime,
        end_time=payload.endTime,
        sla_due_at=payload.slaDueAt or default_sla_due(payload.severity, payload.startTime),
        short_summary=payload.shortSummary,
        detailed_narrative=payload.detailedNarrative,
        recommended_actions=payload.recommendedActions,
        review_notes=payload.reviewNotes,
        evidence_thumbnail_url=payload.evidence.thumbnailUrl,
        evidence_clip_url=payload.evidence.clipUrl,
        evidence_restricted=payload.evidence.restricted,
        assigned_to=payload.assignedTo,
        model_provider=payload.modelProvider,
        model_version=payload.modelVersion,
        detection_summary=payload.detectionSummary,
        created_at=now,
        updated_at=now,
    )
    session.add(incident)
    record_incident_event(
        session, incident, actor=actor, action="created", to_status=payload.status
    )
    # Outbox rows commit atomically with the incident (see app.notifications).
    enqueue_for_incident(session, incident)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        # Only inspect ownership after an insert conflict; never load or expose
        # another workspace's incident. Core columns intentionally bypass ORM
        # visibility so a foreign primary-key collision can become a 404.
        table = IncidentModel.__table__
        owner = session.scalar(select(table.c.org_id).where(table.c.id == incident_id))
        if owner is None:
            raise
        if owner != source.org_id:
            raise HTTPException(status_code=404, detail='Incident not found') from None
        raise HTTPException(status_code=409, detail='Concurrent incident creation; retry the request',
                            headers={'Retry-After': '1'}) from None
    session.refresh(incident)
    response = serialize_incident(incident)
    publish_event("incident", response.model_dump(mode="json"))
    return response


def _transition(
    session: Session,
    incident: IncidentModel,
    *,
    actor: str,
    action: str,
    to_status: str,
    note: str | None = None,
) -> IncidentModel:
    now = datetime.now(UTC)
    from_status = incident.status
    incident.status = to_status
    incident.updated_at = now

    if to_status in {"acknowledged", "assigned", "in_progress"}:
        incident.ack_time = incident.ack_time or now
    if to_status in {"resolved", "false_positive"}:
        incident.end_time = incident.end_time or now
        incident.resolved_time = now
    if to_status == "escalated":
        incident.escalated_at = now

    record_incident_event(
        session,
        incident,
        actor=actor,
        action=action,
        from_status=from_status,
        to_status=to_status,
        note=note,
    )
    session.commit()
    session.refresh(incident)
    publish_event("incident", serialize_incident(incident).model_dump(mode="json"))
    return incident


@router.patch("/incidents/{incident_id}/acknowledge", response_model=EventRecordResponse)
def acknowledge_incident(
    incident_id: str = Path(...),
    session: Session = Depends(get_db_session),
    principal: Principal = Depends(require_human_operator),
) -> EventRecordResponse:
    actor = _actor_of(principal)
    incident = get_incident_or_404(incident_id, session)
    return serialize_incident(
        _transition(session, incident, actor=actor, action="acknowledge", to_status="acknowledged")
    )


@router.patch("/incidents/{incident_id}/assign", response_model=EventRecordResponse)
def assign_incident(
    payload: IncidentAssignRequest,
    incident_id: str = Path(...),
    session: Session = Depends(get_db_session),
    principal: Principal = Depends(require_human_operator),
) -> EventRecordResponse:
    actor = _actor_of(principal)
    incident = get_incident_or_404(incident_id, session)
    incident.assigned_to = payload.assignee
    return serialize_incident(
        _transition(
            session,
            incident,
            actor=actor,
            action="assign",
            to_status="assigned",
            note=f"Assigned to {payload.assignee}",
        )
    )


@router.patch("/incidents/{incident_id}/resolve", response_model=EventRecordResponse)
def resolve_incident(
    incident_id: str = Path(...),
    session: Session = Depends(get_db_session),
    principal: Principal = Depends(require_human_operator),
) -> EventRecordResponse:
    actor = _actor_of(principal)
    incident = get_incident_or_404(incident_id, session)
    return serialize_incident(
        _transition(session, incident, actor=actor, action="resolve", to_status="resolved")
    )


@router.patch("/incidents/{incident_id}/false-positive", response_model=EventRecordResponse)
def false_positive_incident(
    incident_id: str = Path(...),
    session: Session = Depends(get_db_session),
    principal: Principal = Depends(require_human_operator),
) -> EventRecordResponse:
    actor = _actor_of(principal)
    incident = get_incident_or_404(incident_id, session)
    return serialize_incident(
        _transition(
            session, incident, actor=actor, action="false_positive", to_status="false_positive"
        )
    )


@router.patch("/incidents/{incident_id}/status", response_model=EventRecordResponse)
def update_incident_status(
    payload: IncidentStatusUpdateRequest,
    incident_id: str = Path(...),
    session: Session = Depends(get_db_session),
    principal: Principal = Depends(require_human_operator),
) -> EventRecordResponse:
    actor = _actor_of(principal)
    if payload.status not in INCIDENT_STATUSES:
        raise HTTPException(status_code=422, detail="Unsupported status")
    incident = get_incident_or_404(incident_id, session)
    return serialize_incident(
        _transition(
            session,
            incident,
            actor=actor,
            action="status_change",
            to_status=payload.status,
            note=payload.note,
        )
    )


@router.post(
    "/incidents/{incident_id}/comments",
    response_model=IncidentCommentResponse,
    status_code=201,
)
def add_incident_comment(
    payload: IncidentCommentCreateRequest,
    incident_id: str = Path(...),
    session: Session = Depends(get_db_session),
    principal: Principal = Depends(require_human_operator),
) -> IncidentCommentResponse:
    actor = _actor_of(principal)
    incident = get_incident_or_404(incident_id, session)
    comment = IncidentCommentModel(
        id=new_id("cmt"),
        incident_id=incident.id,
        author=actor,
        body=payload.body,
        created_at=datetime.now(UTC),
    )
    session.add(comment)
    record_incident_event(session, incident, actor=actor, action="comment", note=payload.body[:160])
    incident.updated_at = comment.created_at
    session.commit()
    session.refresh(comment)
    session.refresh(incident)
    # Other open browsers re-read the incident (and its timeline) on this event.
    publish_event("incident", serialize_incident(incident).model_dump(mode="json"))
    return serialize_incident_comment(comment)
