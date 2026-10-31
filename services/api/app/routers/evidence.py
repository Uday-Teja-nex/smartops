from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.auth import Principal, require_supervisor, require_viewer
from app.config import get_settings
from app.tenancy import get_tenant_session as get_db_session
from app.ids import new_id
from app.models import EvidenceItemModel, IncidentModel, SourceModel
from app.schemas import (
    EvidenceItemCreateRequest,
    EvidenceItemResponse,
    EvidenceUrlResponse,
)
from app.serializers import serialize_evidence_item

router = APIRouter(prefix="/v1", tags=["evidence"], dependencies=[Depends(require_viewer)])
settings = get_settings()


@router.post("/evidence", response_model=EvidenceItemResponse, status_code=201)
def create_evidence_item(
    payload: EvidenceItemCreateRequest,
    session: Session = Depends(get_db_session),
    _: Principal = Depends(require_supervisor),
) -> EvidenceItemResponse:
    source = session.get(SourceModel, payload.sourceId)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    if payload.incidentId:
        incident = session.get(IncidentModel, payload.incidentId)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        if incident.source_id != source.id:
            raise HTTPException(status_code=422, detail="Evidence source does not match incident")
        if payload.candidateId and payload.candidateId != incident.candidate_id:
            raise HTTPException(status_code=422, detail="Evidence candidate does not match incident")

    item = EvidenceItemModel(
        id=new_id("evd"),
        org_id=source.org_id,
        incident_id=payload.incidentId,
        source_id=payload.sourceId,
        candidate_id=payload.candidateId,
        kind=payload.kind,
        object_key=payload.objectKey,
        content_type=payload.contentType,
        width=payload.width,
        height=payload.height,
        duration_seconds=payload.durationSeconds,
        size_bytes=payload.sizeBytes,
        restricted=payload.restricted,
        meta=payload.meta,
        created_at=datetime.now(UTC),
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    return serialize_evidence_item(item)


@router.get("/evidence", response_model=list[EvidenceItemResponse])
def list_evidence(
    session: Session = Depends(get_db_session),
    incident_id: str | None = Query(default=None, alias="incidentId"),
    candidate_id: str | None = Query(default=None, alias="candidateId"),
    source_id: str | None = Query(default=None, alias="sourceId"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[EvidenceItemResponse]:
    query = select(EvidenceItemModel).order_by(EvidenceItemModel.created_at.desc()).limit(limit)
    if incident_id:
        incident = session.get(IncidentModel, incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        conditions = [EvidenceItemModel.incident_id == incident_id]
        if incident.candidate_id:
            conditions.append(EvidenceItemModel.candidate_id == incident.candidate_id)
        query = query.where(or_(*conditions), EvidenceItemModel.source_id == incident.source_id)
    if candidate_id:
        query = query.where(EvidenceItemModel.candidate_id == candidate_id)
    if source_id:
        query = query.where(EvidenceItemModel.source_id == source_id)
    items = session.scalars(query).all()
    return [serialize_evidence_item(item) for item in items]


@router.get("/evidence/{evidence_id}/url", response_model=EvidenceUrlResponse)
def get_evidence_url(
    evidence_id: str,
    session: Session = Depends(get_db_session),
) -> EvidenceUrlResponse:
    """Issue a short-lived presigned URL for one evidence object.

    Access control today: restricted evidence is still served because auth
    lands in the RBAC phase; the access path is centralized here so role
    checks bolt on in one place.
    """
    item = session.get(EvidenceItemModel, evidence_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if not settings.evidence_storage_enabled:
        raise HTTPException(status_code=503, detail="Evidence storage is disabled")

    from app.storage import presign_get_url

    try:
        url = presign_get_url(item.object_key)
    except Exception as exc:  # noqa: BLE001 - storage outage surfaces as 503.
        raise HTTPException(status_code=503, detail=f"Object storage unavailable: {exc}") from exc

    return EvidenceUrlResponse(
        id=item.id,
        url=url,
        expiresInSeconds=settings.evidence_url_ttl_seconds,
    )
