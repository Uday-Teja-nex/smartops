from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db import engine
from app.models import UserModel


def test_existing_token_obeys_disabled_account_and_role_changes(client, admin_headers):
    with Session(engine) as session:
        user = session.scalars(select(UserModel).where(UserModel.email == 'admin@smartops.local')).one()
        user_id = user.id
        user.active = False
        session.commit()
    try:
        assert client.get('/v1/users', headers=admin_headers).status_code == 401
        with Session(engine) as session:
            user = session.get(UserModel, user_id)
            user.active = True
            user.role = 'viewer'
            session.commit()
        assert client.get('/v1/users', headers=admin_headers).status_code == 403
        assert client.get('/v1/auth/me', headers=admin_headers).json()['role'] == 'viewer'
    finally:
        with Session(engine) as session:
            user = session.get(UserModel, user_id)
            user.active = True
            user.role = 'admin'
            session.commit()


def test_service_cannot_resolve_human_incident(client, service_headers):
    assert client.patch('/v1/incidents/nonexistent/resolve', headers=service_headers).status_code == 403
