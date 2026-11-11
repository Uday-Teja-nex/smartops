"""Workspace user management and self-service password change.

There is no email delivery, so an invite returns a one-time temporary
password exactly once; the admin hands it over and the user changes it.
Admins cannot deactivate or demote themselves, so a workspace always keeps
at least the admin who is acting. Deactivation and password resets end the
affected user's sessions immediately.
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth import Principal, get_current_principal, require_admin
from app.db import get_db_session
from app.ids import new_id
from app.models import AuthSessionModel, UserModel
from app.schemas import UserResponse
from app.security import hash_password, verify_password
from app.serializers import serialize_user

router = APIRouter(prefix="/v1", tags=["users"])

Role = Literal["admin", "supervisor", "operator", "viewer", "security", "ehs"]
MIN_PASSWORD = 12


class InviteRequest(BaseModel):
    email: str = Field(min_length=3, max_length=160, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: str = Field(min_length=1, max_length=160)
    role: Role


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    role: Role | None = None
    active: bool | None = None


class PasswordChange(BaseModel):
    currentPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=MIN_PASSWORD, max_length=128)


def temporary_password() -> str:
    return secrets.token_urlsafe(12)


def revoke_sessions(session: Session, user_id: str, reason: str, keep: str | None = None) -> None:
    query = update(AuthSessionModel).where(AuthSessionModel.user_id == user_id, AuthSessionModel.revoked_at.is_(None))
    if keep:
        query = query.where(AuthSessionModel.id != keep)
    session.execute(query.values(revoked_at=datetime.now(UTC), revoked_reason=reason))


def _member(session: Session, principal: Principal, user_id: str) -> UserModel:
    user = session.get(UserModel, user_id)
    if user is None or user.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.post("/users", status_code=201)
def invite_user(payload: InviteRequest, session: Session = Depends(get_db_session),
                principal: Principal = Depends(require_admin)) -> dict:
    email = payload.email.strip().lower()
    if session.scalar(select(UserModel.id).where(UserModel.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    password = temporary_password()
    user = UserModel(id=new_id("usr"), org_id=principal.org_id, email=email, name=payload.name.strip(),
                     password_hash=hash_password(password), role=payload.role, active=True,
                     created_at=datetime.now(UTC))
    session.add(user)
    session.commit()
    return {"user": serialize_user(user).model_dump(), "temporaryPassword": password}


@router.patch("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: str, payload: UserUpdate, session: Session = Depends(get_db_session),
                principal: Principal = Depends(require_admin)) -> UserResponse:
    user = _member(session, principal, user_id)
    if user.id == principal.id and (payload.active is False or (payload.role and payload.role != "admin")):
        raise HTTPException(status_code=409, detail="You cannot deactivate or demote your own account")
    if payload.name is not None:
        user.name = payload.name.strip()
    if payload.role is not None:
        user.role = payload.role
    if payload.active is not None:
        user.active = payload.active
        if not payload.active:
            revoke_sessions(session, user.id, "deactivated")
    session.commit()
    return serialize_user(user)


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: str, session: Session = Depends(get_db_session),
                   principal: Principal = Depends(require_admin)) -> dict:
    user = _member(session, principal, user_id)
    password = temporary_password()
    user.password_hash = hash_password(password)
    revoke_sessions(session, user.id, "password_reset")
    session.commit()
    return {"temporaryPassword": password}


@router.post("/auth/password", status_code=204, response_class=Response)
def change_own_password(payload: PasswordChange, session: Session = Depends(get_db_session),
                        principal: Principal = Depends(get_current_principal)) -> Response:
    if principal.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")
    user = session.get(UserModel, principal.id)
    if user is None or not verify_password(payload.currentPassword, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.newPassword == payload.currentPassword:
        raise HTTPException(status_code=422, detail="Choose a different password")
    user.password_hash = hash_password(payload.newPassword)
    # Stay signed in here; sign out everywhere else.
    revoke_sessions(session, user.id, "password_changed", keep=principal.session_id)
    session.commit()
    return Response(status_code=204)
