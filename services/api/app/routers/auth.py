from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, authenticate_user, create_access_token, get_current_principal, require_admin
from app.db import get_db_session
from app.models import UserModel
from app.schemas import UserResponse
from app.serializers import serialize_user
from app.login_limits import enforce_login_limit
from app.config import get_settings
from app.sessions import (
    REFRESH_COOKIE,
    REFRESH_COOKIE_PATH,
    RefreshRejected,
    open_session,
    revoke_by_id,
    revoke_by_refresh,
    rotate_session,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])
users_router = APIRouter(prefix="/v1", tags=["users"])


@router.post('/stream-ticket')
def stream_ticket(response: Response, principal: Principal = Depends(get_current_principal)):
    from datetime import UTC, datetime, timedelta
    import jwt
    from app.config import get_settings
    if principal.kind != 'user':
        raise HTTPException(status_code=403, detail='User session required')
    expires = datetime.now(UTC) + timedelta(seconds=30)
    token = jwt.encode({'sub': principal.id, 'org': principal.org_id, 'aud': 'incident-stream',
                        'sid': principal.session_id, 'exp': expires}, get_settings().jwt_secret, algorithm='HS256')
    response.headers['Cache-Control'] = 'no-store'
    return {'ticket': token, 'expiresInSeconds': 30}


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str
    expiresInSeconds: int
    user: UserResponse


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_ttl_hours * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True,
                           secure=settings.refresh_cookie_secure, samesite="strict")
    response.headers["Cache-Control"] = "no-store"


def _issue(user: UserModel, session_id: str) -> LoginResponse:
    return LoginResponse(token=create_access_token(user, session_id),
                         expiresInSeconds=get_settings().jwt_ttl_minutes * 60,
                         user=serialize_user(user))


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response,
          session: Session = Depends(get_db_session)) -> LoginResponse:
    email = payload.email.strip().lower()
    enforce_login_limit(request.client.host if request.client else 'unknown', email)
    user = authenticate_user(session, email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    record, refresh = open_session(session, user)
    session.commit()
    _set_refresh_cookie(response, refresh)
    return _issue(user, record.id)


@router.post("/refresh", response_model=LoginResponse)
def refresh(response: Response, session: Session = Depends(get_db_session),
            smartops_refresh: str | None = Cookie(default=None)) -> LoginResponse:
    if not smartops_refresh:
        raise HTTPException(status_code=401, detail="Sign in required")
    try:
        record, user, token = rotate_session(session, smartops_refresh)
    except RefreshRejected as exc:
        _clear_refresh_cookie(response)
        # HTTPException discards `response`; send the cookie clear explicitly.
        raise HTTPException(
            status_code=401, detail=str(exc),
            headers={"Set-Cookie": f"{REFRESH_COOKIE}=; Max-Age=0; Path={REFRESH_COOKIE_PATH}; HttpOnly; SameSite=strict"
                     + ("; Secure" if get_settings().refresh_cookie_secure else "")},
        ) from exc
    session.commit()
    _set_refresh_cookie(response, token)
    return _issue(user, record.id)


@router.post("/logout", status_code=204)
def logout(request: Request, session: Session = Depends(get_db_session),
           smartops_refresh: str | None = Cookie(default=None)) -> Response:
    """Revoke this browser's session. Works with the refresh cookie, a bearer
    token, or both; never fails so a stale client can always sign out."""
    if smartops_refresh:
        revoke_by_refresh(session, smartops_refresh)
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        try:
            from app.auth import _principal_from_token
            claims = _principal_from_token(authorization[7:].strip())
            if claims.session_id:
                revoke_by_id(session, claims.session_id, claims.id)
        except HTTPException:
            pass
    session.commit()
    response = Response(status_code=204)
    _clear_refresh_cookie(response)
    return response


@router.get("/me", response_model=UserResponse)
def me(
    principal: Principal = Depends(get_current_principal),
    session: Session = Depends(get_db_session),
) -> UserResponse:
    if principal.kind == "service":
        return UserResponse(
            id=principal.id,
            email=principal.email,
            name=principal.name,
            role=principal.role,
            active=True,
        )
    user = session.get(UserModel, principal.id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_user(user)


@users_router.get("/users", response_model=list[UserResponse])
def list_users(
    session: Session = Depends(get_db_session),
    principal: Principal = Depends(require_admin),
) -> list[UserResponse]:
    users = session.scalars(select(UserModel).where(UserModel.org_id == principal.org_id).order_by(UserModel.email)).all()
    return [serialize_user(user) for user in users]
