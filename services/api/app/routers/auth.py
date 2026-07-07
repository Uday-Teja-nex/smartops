from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Principal, authenticate_user, create_access_token, get_current_principal, require_admin
from app.db import get_db_session
from app.models import UserModel
from app.schemas import UserResponse
from app.serializers import serialize_user

router = APIRouter(prefix="/v1/auth", tags=["auth"])
users_router = APIRouter(prefix="/v1", tags=["users"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    token: str
    user: UserResponse


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, session: Session = Depends(get_db_session)) -> LoginResponse:
    user = authenticate_user(session, payload.email.lower(), payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return LoginResponse(token=create_access_token(user), user=serialize_user(user))


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
    _: Principal = Depends(require_admin),
) -> list[UserResponse]:
    users = session.scalars(select(UserModel).order_by(UserModel.email)).all()
    return [serialize_user(user) for user in users]
