"""Create a client workspace in one request, for personalizing a prospect demo.

Only platform administrators (SMARTOPS_PLATFORM_ADMIN_EMAILS) may do this.
The new workspace gets its topology, admin/operator/viewer accounts, and
optionally a copy of an existing recorded camera (same stream and zones) and
a phone camera, so it shows live incidents within minutes.
"""
from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, require_admin
from app.config import get_settings
from app.db import get_db_session
from app.ids import new_id
from app.models import (BuildingModel, FloorModel, OrganizationModel, SourceModel, UserModel, ZoneModel)
from app.security import hash_password

router = APIRouter(prefix="/v1", tags=["workspaces"])


def is_platform_admin(principal: Principal) -> bool:
    allowed = {email.strip().lower() for email in get_settings().platform_admin_emails.split(",") if email.strip()}
    return principal.kind == "user" and principal.role == "admin" and principal.email.lower() in allowed


def require_platform_admin(principal: Principal = Depends(require_admin)) -> Principal:
    if not is_platform_admin(principal):
        raise HTTPException(status_code=403, detail="Only platform administrators can create workspaces")
    return principal


class FloorInput(BaseModel):
    level: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=120)
    zones: list[str] = Field(default_factory=list, max_length=20)


class WorkspaceInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    accent: str = Field(default="#38bdf8", pattern=r"^#[0-9a-fA-F]{6}$")
    buildingName: str = Field(min_length=1, max_length=120)
    address: str = Field(default="", max_length=160)
    timezone: str = Field(default="Asia/Kolkata", max_length=64)
    floors: list[FloorInput] = Field(min_length=1, max_length=20)
    password: str = Field(min_length=10, max_length=128)
    copyCameraId: str | None = None
    addPhoneCamera: bool = False

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Unknown timezone") from exc
        return value


class Account(BaseModel):
    email: str
    role: Literal["admin", "operator", "viewer"]


class WorkspaceCreated(BaseModel):
    id: str
    name: str
    accounts: list[Account]
    cameras: list[str]


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    return slug or "workspace"


@router.get("/workspaces/capabilities")
def capabilities(session: Session = Depends(get_db_session), principal: Principal = Depends(require_admin)) -> dict:
    if not is_platform_admin(principal):
        return {"canCreateWorkspaces": False, "copyableCameras": []}
    recorded = session.scalars(select(SourceModel).where(SourceModel.source_type == "rtsp")).all()
    orgs = {org.id: org.name for org in session.scalars(select(OrganizationModel)).all()}
    cameras = [{"id": source.id, "name": source.name, "workspace": orgs.get(source.org_id, source.org_id),
                "zones": len((source.detection_config or {}).get("zones", []))}
               for source in recorded if "recorded-loop" in (source.tags or []) and source.enabled]
    return {"canCreateWorkspaces": True, "copyableCameras": cameras}


@router.post("/workspaces", response_model=WorkspaceCreated, status_code=201)
def create_workspace(payload: WorkspaceInput, session: Session = Depends(get_db_session),
                     principal: Principal = Depends(require_platform_admin)) -> WorkspaceCreated:
    now = datetime.now(UTC)
    base = slugify(payload.name)
    slug = base
    while session.scalar(select(OrganizationModel.id).where(OrganizationModel.slug == slug)):
        slug = f"{base}-{secrets.token_hex(2)}"
    org_id = f"org-{slug}"
    org = OrganizationModel(id=org_id, name=payload.name.strip(), slug=slug,
                            settings={"accent": payload.accent, "createdBy": principal.email}, created_at=now)
    session.add(org)
    session.flush()

    accounts: list[Account] = []
    password_hash = hash_password(payload.password)
    for role, person in (("admin", "Workspace Admin"), ("operator", "Duty Operator"), ("viewer", "Read-only Viewer")):
        email = f"{role}@{slug}.demo"
        if session.scalar(select(UserModel.id).where(UserModel.email == email)):
            raise HTTPException(status_code=409, detail=f"Account {email} already exists")
        session.add(UserModel(id=new_id("usr"), org_id=org_id, email=email, name=person,
                              password_hash=password_hash, role=role, active=True, created_at=now))
        accounts.append(Account(email=email, role=role))

    building = BuildingModel(id=new_id("bldg"), org_id=org_id, name=payload.buildingName.strip(),
                             address=payload.address.strip() or payload.buildingName.strip(),
                             timezone=payload.timezone)
    session.add(building)
    session.flush()
    first_floor = None
    first_zone = None
    for floor_input in payload.floors:
        floor = FloorModel(id=new_id("flr"), building_id=building.id, level=floor_input.level.strip(),
                           name=floor_input.name.strip())
        session.add(floor)
        session.flush()
        first_floor = first_floor or floor
        for zone_name in floor_input.zones:
            if not zone_name.strip():
                continue
            zone = ZoneModel(id=new_id("zone"), floor_id=floor.id, name=zone_name.strip()[:120], kind="zone")
            session.add(zone)
            if floor is first_floor and first_zone is None:
                first_zone = zone
    session.flush()

    cameras: list[str] = []

    def add_camera(name: str, uri: str, config: dict, tags: list[str], notes: str) -> None:
        session.add(SourceModel(
            id=new_id("src"), org_id=org_id, building_id=building.id, floor_id=first_floor.id,
            zone_id=first_zone.id if first_zone else None, floor_label=first_floor.level,
            zone_label=first_zone.name if first_zone else first_floor.name, name=name, source_type="rtsp",
            source_uri=uri, input_format="h264", credentials_ref=None, enabled=True, status="offline", health={},
            tags=tags, position_notes=notes, detection_config=config, created_at=now, updated_at=now))
        cameras.append(name)

    if payload.copyCameraId:
        # Platform admins may copy any workspace's recorded camera (stream + zones).
        template = session.get(SourceModel, payload.copyCameraId)
        if template is None or template.source_type != "rtsp":
            raise HTTPException(status_code=404, detail="Camera to copy not found")
        add_camera(template.name, template.source_uri, dict(template.detection_config or {}),
                   ["copied-camera", *template.tags],
                   f"Copy of '{template.name}' for this demo workspace; same stream and zones.")
    if payload.addPhoneCamera:
        path = f"phone-{secrets.token_hex(3)}"
        add_camera("Phone camera", f"rtsp://{get_settings().mediamtx_rtsp_host}:8554/{path}", {}, ["phone"],
                   "Phone camera publishing over RTMP from the local network.")
    session.commit()
    return WorkspaceCreated(id=org_id, name=org.name, accounts=accounts, cameras=cameras)
