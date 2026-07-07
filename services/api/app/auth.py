"""Authentication and role-based access control.

Principals:
  - Users authenticate with email/password and receive a JWT (Bearer).
  - Pipeline services (worker, video-ingest, orchestrator callbacks)
    authenticate with a shared internal token header. They act as the
    'service' principal and may write pipeline data but are not operators.
  - SSE connections pass the JWT as a `token` query parameter because
    EventSource cannot set headers.

Role ladder (ascending): viewer < security/ehs/operator < supervisor < admin.
security/ehs are operator-level but scoped by page in the UI; the API treats
them as operators for incident actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db_session
from app.models import UserModel

settings = get_settings()

ROLE_LEVELS: dict[str, int] = {
    "viewer": 0,
    "security": 1,
    "ehs": 1,
    "operator": 1,
    "supervisor": 2,
    "admin": 3,
    "service": 2,  # pipeline services may write pipeline data
}


@dataclass
class Principal:
    id: str
    name: str
    email: str
    role: str
    org_id: str
    kind: str  # "user" | "service"

    @property
    def level(self) -> int:
        return ROLE_LEVELS.get(self.role, -1)


SERVICE_PRINCIPAL = Principal(
    id="svc-pipeline",
    name="SmartOps Pipeline",
    email="pipeline@smartops.internal",
    role="service",
    org_id="org-demo",
    kind="service",
)


def create_access_token(user: UserModel) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "org": user.org_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _principal_from_token(token: str) -> Principal:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    return Principal(
        id=str(payload.get("sub", "")),
        name=str(payload.get("name", "")),
        email=str(payload.get("email", "")),
        role=str(payload.get("role", "viewer")),
        org_id=str(payload.get("org", "")),
        kind="user",
    )


def get_current_principal(
    authorization: str | None = Header(default=None),
    x_internal_token: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> Principal:
    if x_internal_token:
        if x_internal_token != settings.internal_token:
            raise HTTPException(status_code=401, detail="Invalid internal token")
        return SERVICE_PRINCIPAL

    bearer = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer = authorization[7:].strip()
    raw = bearer or token
    if not raw:
        raise HTTPException(status_code=401, detail="Authentication required")
    return _principal_from_token(raw)


def require_role(minimum: str, *, allow_service: bool = True):
    """Dependency factory: principal must be at/above `minimum` role level."""
    minimum_level = ROLE_LEVELS[minimum]

    def dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.kind == "service":
            if allow_service:
                return principal
            raise HTTPException(status_code=403, detail="Service tokens cannot perform this action")
        if principal.level < minimum_level:
            raise HTTPException(
                status_code=403,
                detail=f"Requires {minimum} role or higher (you are {principal.role})",
            )
        return principal

    return dependency


require_viewer = require_role("viewer")
require_operator = require_role("operator")
require_supervisor = require_role("supervisor")
require_admin = require_role("admin", allow_service=False)


def authenticate_user(session: Session, email: str, password: str) -> UserModel | None:
    from app.security import verify_password

    user = session.scalars(select(UserModel).where(UserModel.email == email)).first()
    if user is None or not user.active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_db() -> Session:  # re-export for router convenience
    yield from get_db_session()
