"""Reset returns a populated database to exactly the seeded state.

Runs on a private in-memory database: a real reset revokes every sign-in,
which would break the session-scoped login fixtures other tests share.
"""

from datetime import UTC, datetime

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base
from app.models import AuthSessionModel, IncidentModel, OrganizationModel, SourceModel
from app.seed import seed_workspaces


def test_reset_clears_pipeline_rows_sessions_and_reseeds(monkeypatch):
    from app import reset_demo
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    now = datetime.now(UTC)
    with Session() as session:
        seed_workspaces(session, {"mall-store": "clip.mp4"})
        session.add(IncidentModel(
            id="inc-x", org_id="org-mall", category="Security", event_type="loitering", severity="low",
            confidence=1, status="active", building_id="bldg-mall-01", floor="G", zone="Store",
            source_id="src-mall-store", start_time=now, sla_due_at=now, short_summary="x",
            detailed_narrative=[], recommended_actions=[], review_notes=[], evidence_thumbnail_url="",
            evidence_clip_url="", evidence_restricted=False, model_provider="rule-engine", model_version="t",
            detection_summary={}, created_at=now, updated_at=now))
        session.add(AuthSessionModel(id="ses-x", org_id="org-mall", user_id="usr-mall-admin", refresh_hash="h",
                                     created_at=now, last_used_at=now, expires_at=now))
        session.commit()
    monkeypatch.setattr(reset_demo, "engine", engine)
    monkeypatch.setattr(reset_demo, "SessionLocal", Session)
    monkeypatch.setattr(reset_demo, "published_paths", lambda: {})
    monkeypatch.setattr(reset_demo, "clear_evidence", lambda: 0)
    assert reset_demo.main() == 0
    with Session() as session:
        assert session.scalar(select(func.count(IncidentModel.id))) == 0
        assert session.scalar(select(func.count(AuthSessionModel.id))) == 0
        assert {org.id for org in session.scalars(select(OrganizationModel))} == {
            "org-demo", "org-mall", "org-campus"}
        # Reseeded from the current manifest (empty here), not the old state.
        assert not session.get(SourceModel, "src-mall-store").enabled


def test_reset_refuses_production(monkeypatch):
    from app import reset_demo
    monkeypatch.setattr(reset_demo, "get_settings", lambda: type("S", (), {"environment": "production"})())
    assert reset_demo.main() == 2
