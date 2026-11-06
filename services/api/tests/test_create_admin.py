"""First-admin bootstrap for production installs (no demo seeding)."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import OrganizationModel, UserModel
from app.security import verify_password


def test_creates_workspace_and_admin_once(monkeypatch, capsys):
    from app import create_admin
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(create_admin, "SessionLocal", sessionmaker(bind=engine))
    monkeypatch.delenv("SMARTOPS_ADMIN_PASSWORD", raising=False)
    assert create_admin.main(["--workspace", "Acme Facilities", "--email", "Ops@Acme.example"]) == 2
    monkeypatch.setenv("SMARTOPS_ADMIN_PASSWORD", "a-long-enough-secret")
    assert create_admin.main(["--workspace", "Acme Facilities", "--email", "Ops@Acme.example"]) == 0
    assert create_admin.main(["--workspace", "Acme Facilities", "--email", "ops@acme.example"]) == 0
    assert "already exists" in capsys.readouterr().out
    with sessionmaker(bind=engine)() as session:
        users = session.scalars(select(UserModel)).all()
        assert [(u.email, u.role, u.org_id) for u in users] == [("ops@acme.example", "admin", "org-acme-facilities")]
        assert verify_password("a-long-enough-secret", users[0].password_hash)
        assert session.get(OrganizationModel, "org-acme-facilities").name == "Acme Facilities"
