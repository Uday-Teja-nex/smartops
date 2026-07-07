from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, require_supervisor, require_viewer
from app.config import get_settings
from app.db import get_db_session
from app.models import OrganizationModel

router = APIRouter(prefix="/v1", tags=["organization"], dependencies=[Depends(require_viewer)])
settings = get_settings()


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    settings: dict[str, Any] = Field(default_factory=dict)


class OrgSettingsUpdateRequest(BaseModel):
    settings: dict[str, Any]


class RuntimeConfigResponse(BaseModel):
    modelProvider: str
    orchestrator: str
    evidenceStorageEnabled: bool
    evidenceUrlTtlSeconds: int


def _get_org(session: Session) -> OrganizationModel:
    org = session.scalars(select(OrganizationModel).limit(1)).first()
    if org is None:
        raise HTTPException(status_code=404, detail="No organization configured")
    return org


@router.get("/org", response_model=OrgResponse)
def get_org(session: Session = Depends(get_db_session)) -> OrgResponse:
    org = _get_org(session)
    return OrgResponse(id=org.id, name=org.name, slug=org.slug, settings=org.settings or {})


@router.put("/org/settings", response_model=OrgResponse)
def update_org_settings(
    payload: OrgSettingsUpdateRequest,
    session: Session = Depends(get_db_session),
    _: Principal = Depends(require_supervisor),
) -> OrgResponse:
    org = _get_org(session)
    org.settings = {**(org.settings or {}), **payload.settings}
    session.commit()
    session.refresh(org)
    return OrgResponse(id=org.id, name=org.name, slug=org.slug, settings=org.settings or {})


@router.get("/config", response_model=RuntimeConfigResponse)
def runtime_config() -> RuntimeConfigResponse:
    return RuntimeConfigResponse(
        modelProvider=settings.model_provider,
        orchestrator=settings.orchestrator_name,
        evidenceStorageEnabled=settings.evidence_storage_enabled,
        evidenceUrlTtlSeconds=settings.evidence_url_ttl_seconds,
    )
