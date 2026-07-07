from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import require_viewer
from app.config import get_settings
from app.db import get_db_session
from app.models import BuildingModel, FloorModel, IncidentModel, SourceModel
from app.schemas import BootstrapResponse, RuntimeSummaryResponse
from app.serializers import (
    serialize_building,
    serialize_incident,
    serialize_source,
    serialize_source_as_camera,
)

router = APIRouter(prefix="/v1", tags=["bootstrap"], dependencies=[Depends(require_viewer)])
settings = get_settings()


@router.get("/bootstrap", response_model=BootstrapResponse)
def get_bootstrap(session: Session = Depends(get_db_session)) -> BootstrapResponse:
    buildings = session.scalars(
        select(BuildingModel)
        .options(selectinload(BuildingModel.floors).selectinload(FloorModel.zones))
        .order_by(BuildingModel.name)
    ).all()
    sources = session.scalars(select(SourceModel).order_by(SourceModel.name)).all()
    incidents = session.scalars(
        select(IncidentModel).order_by(IncidentModel.start_time.desc()).limit(200)
    ).all()

    runtime = RuntimeSummaryResponse(
        backendMode="live",
        orchestrator=settings.orchestrator_name,
        modelProvider=settings.model_provider,
        activeSourceCount=sum(
            1 for source in sources if source.enabled and source.status in {"online", "processing"}
        ),
        totalSourceCount=len(sources),
    )

    return BootstrapResponse(
        buildings=[serialize_building(building) for building in buildings],
        cameras=[serialize_source_as_camera(source) for source in sources],
        sources=[serialize_source(source) for source in sources],
        incidents=[serialize_incident(incident) for incident in incidents],
        runtime=runtime,
    )
