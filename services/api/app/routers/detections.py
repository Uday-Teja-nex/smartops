from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, require_supervisor, require_viewer
from app.tenancy import get_tenant_session as get_db_session
from app.ids import new_id
from app.models import DetectionModel, SourceModel
from app.schemas import DetectionBatchCreateRequest, DetectionResponse
from app.serializers import serialize_detection

router = APIRouter(prefix="/v1", tags=["detections"], dependencies=[Depends(require_viewer)])


@router.post("/detections", response_model=list[DetectionResponse], status_code=201)
def create_detections(
    payload: DetectionBatchCreateRequest,
    session: Session = Depends(get_db_session),
    _: Principal = Depends(require_supervisor),
) -> list[DetectionResponse]:
    if not payload.detections:
        return []

    source_ids = {item.sourceId for item in payload.detections}
    sources = {
        source.id: source
        for source in session.scalars(
            select(SourceModel).where(SourceModel.id.in_(source_ids))
        ).all()
    }
    missing = source_ids - sources.keys()
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown source ids: {sorted(missing)}")

    now = datetime.now(UTC)
    models: list[DetectionModel] = []
    for item in payload.detections:
        models.append(
            DetectionModel(
                id=new_id("det"),
                org_id=sources[item.sourceId].org_id,
                source_id=item.sourceId,
                candidate_id=item.candidateId,
                label=item.label,
                confidence=item.confidence,
                bbox_x=item.bbox.x,
                bbox_y=item.bbox.y,
                bbox_w=item.bbox.w,
                bbox_h=item.bbox.h,
                frame_ts=item.frameTs,
                frame_index=item.frameIndex,
                model_name=item.modelName,
                created_at=now,
            )
        )
    session.add_all(models)
    session.commit()
    return [serialize_detection(model) for model in models]


@router.get("/detections", response_model=list[DetectionResponse])
def list_detections(
    session: Session = Depends(get_db_session),
    candidate_id: str | None = Query(default=None, alias="candidateId"),
    source_id: str | None = Query(default=None, alias="sourceId"),
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[DetectionResponse]:
    query = (
        select(DetectionModel)
        .order_by(DetectionModel.created_at.desc(), DetectionModel.frame_ts)
        .limit(limit)
    )
    if candidate_id:
        query = query.where(DetectionModel.candidate_id == candidate_id)
    if source_id:
        query = query.where(DetectionModel.source_id == source_id)
    detections = session.scalars(query).all()
    return [serialize_detection(model) for model in detections]
