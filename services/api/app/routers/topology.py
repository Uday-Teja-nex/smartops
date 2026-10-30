from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import Principal, require_viewer
from app.tenancy import get_tenant_session as get_db_session
from app.models import BuildingModel, FloorModel
from app.schemas import BuildingResponse
from app.serializers import serialize_building

router = APIRouter(prefix="/v1", tags=["topology"], dependencies=[Depends(require_viewer)])


@router.get("/buildings", response_model=list[BuildingResponse])
def list_buildings(session: Session = Depends(get_db_session), principal: Principal = Depends(require_viewer)) -> list[BuildingResponse]:
    buildings = session.scalars(
        select(BuildingModel)
        .where(BuildingModel.org_id == principal.org_id)
        .options(selectinload(BuildingModel.floors).selectinload(FloorModel.zones))
        .order_by(BuildingModel.name)
    ).all()
    return [serialize_building(building) for building in buildings]
