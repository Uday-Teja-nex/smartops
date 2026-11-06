"""Demo seed: three workspaces, honest camera states, valid zone rules."""

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import IncidentModel, OrganizationModel, SourceModel, UserModel
from app.seed import seed_workspaces
from app.zone_config import Zone


def seeded(publishing):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = Session(engine)
    seed_workspaces(session, publishing)
    return session


def test_three_workspaces_with_a_full_role_ladder_each():
    session = seeded({})
    orgs = {org.id: org for org in session.scalars(select(OrganizationModel))}
    assert set(orgs) == {"org-demo", "org-mall", "org-campus"}
    for org_id in orgs:
        roles = set(session.scalars(select(UserModel.role).where(UserModel.org_id == org_id)))
        assert roles == {"admin", "supervisor", "operator", "viewer", "security", "ehs"}
    assert session.scalar(select(UserModel.org_id).where(UserModel.email == "operator@mall.demo")) == "org-mall"
    assert session.scalar(select(func.count(IncidentModel.id))) == 0


def test_only_cameras_with_published_footage_are_enabled():
    session = seeded({"mall-store": "first test video.mp4"})
    sources = session.scalars(select(SourceModel)).all()
    enabled = [source.id for source in sources if source.enabled]
    assert enabled == ["src-mall-store"]
    assert all(source.source_type == "rtsp" and source.source_uri.startswith("rtsp://mediamtx:8554/")
               for source in sources)
    waiting = [source for source in sources if not source.enabled]
    assert waiting and all("No footage assigned yet" in source.position_notes for source in waiting)
    assert all(source.org_id == {"bldg-mall-01": "org-mall"}.get(source.building_id, source.org_id)
               for source in sources)


def test_seeded_zone_rules_pass_the_editor_validator():
    session = seeded({"mall-store": "first test video.mp4"})
    store = session.get(SourceModel, "src-mall-store")
    zones = [Zone.model_validate(zone) for zone in store.detection_config["zones"]]
    assert {zone.id for zone in zones} == {"Checkout queue", "Front aisle", "Promo display"}
    assert {rule.type for zone in zones for rule in zone.rules} == {"queue_build_up", "crowding", "loitering"}


def test_every_seeded_zone_is_valid_and_recorded_cameras_have_rules():
    publishing = {"mall-store": "a.mp4", "mall-atrium": "b.mp4", "office-lobby": "c.mp4", "campus-lab": "d.mp4"}
    session = seeded(publishing)
    enabled = [s for s in session.scalars(select(SourceModel)) if s.enabled]
    assert {s.id for s in enabled} == {"src-mall-store", "src-mall-atrium", "src-office-lobby", "src-campus-lab"}
    for source in enabled:
        zones = [Zone.model_validate(zone) for zone in source.detection_config["zones"]]
        assert zones and all(zone.rules for zone in zones), source.id
    lab = session.get(SourceModel, "src-campus-lab")
    assert lab.detection_config["zones"][0]["rules"][0]["cooldownSeconds"] == 120
