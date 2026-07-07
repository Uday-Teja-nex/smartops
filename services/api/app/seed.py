"""Local demo seed data.

Everything created here is clearly demo scaffolding for local development:
an organization, one user per role (shared demo password), building topology,
and demo sources. Incidents are NOT seeded — they must come from the real
pipeline so the UI never shows fabricated AI output.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    BuildingModel,
    FloorModel,
    OrganizationModel,
    SourceModel,
    UserModel,
    ZoneModel,
)
from app.security import hash_password

DEMO_ORG_ID = "org-demo"
DEMO_PASSWORD = "smartops-demo"

DEMO_USERS = [
    ("usr-admin", "admin@smartops.local", "Avery Admin", "admin"),
    ("usr-supervisor", "supervisor@smartops.local", "Sam Supervisor", "supervisor"),
    ("usr-operator", "operator@smartops.local", "Olivia Operator", "operator"),
    ("usr-viewer", "viewer@smartops.local", "Vik Viewer", "viewer"),
    ("usr-security", "security@smartops.local", "Selin Security", "security"),
    ("usr-ehs", "ehs@smartops.local", "Eli EHS", "ehs"),
]


def seed_database(session: Session) -> None:
    existing_orgs = session.scalar(select(func.count(OrganizationModel.id)))
    if existing_orgs and existing_orgs > 0:
        return

    now = datetime.now(UTC)

    org = OrganizationModel(
        id=DEMO_ORG_ID,
        name="SmartOps Demo Org",
        slug="smartops-demo",
        settings={
            "notificationPreferences": {"email": False, "webhook": False},
            "categoryThresholds": {},
        },
        created_at=now,
    )
    session.add(org)

    for user_id, email, name, role in DEMO_USERS:
        session.add(
            UserModel(
                id=user_id,
                org_id=DEMO_ORG_ID,
                email=email,
                name=name,
                password_hash=hash_password(DEMO_PASSWORD),
                role=role,
                active=True,
                created_at=now,
            )
        )

    buildings = [
        BuildingModel(
            id="bldg-north-01",
            org_id=DEMO_ORG_ID,
            name="Northpoint Tower",
            address="200 Market Plaza",
            timezone="Asia/Kolkata",
        ),
        BuildingModel(
            id="bldg-south-02",
            org_id=DEMO_ORG_ID,
            name="Harbor View",
            address="88 Bay Street",
            timezone="Asia/Kolkata",
        ),
    ]
    session.add_all(buildings)

    floors = [
        FloorModel(id="flr-n01-l1", building_id="bldg-north-01", level="L1", name="Ground Lobby"),
        FloorModel(id="flr-n01-l2", building_id="bldg-north-01", level="L2", name="Amenities"),
        FloorModel(id="flr-s02-l1", building_id="bldg-south-02", level="L1", name="Entrance"),
        FloorModel(id="flr-s02-l5", building_id="bldg-south-02", level="L5", name="Terrace"),
    ]
    session.add_all(floors)

    zones = [
        ZoneModel(id="zone-n01-atrium", floor_id="flr-n01-l1", name="Lobby Atrium", kind="zone"),
        ZoneModel(id="zone-n01-elev", floor_id="flr-n01-l1", name="Elevator Bank", kind="zone"),
        ZoneModel(id="zone-n01-pantry", floor_id="flr-n01-l2", name="Pantry & Cafe", kind="room"),
        ZoneModel(id="zone-n01-restroom", floor_id="flr-n01-l2", name="Restroom Entry", kind="zone"),
        ZoneModel(id="zone-s02-entry", floor_id="flr-s02-l1", name="Main Entry", kind="zone"),
        ZoneModel(id="zone-s02-terrace", floor_id="flr-s02-l5", name="Terrace Entry", kind="zone"),
    ]
    session.add_all(zones)

    sources = [
        # Demo file source pointing at the local sample footage directory.
        SourceModel(
            id="src-demo-lobby",
            org_id=DEMO_ORG_ID,
            building_id="bldg-north-01",
            floor_id="flr-n01-l1",
            zone_id="zone-n01-atrium",
            floor_label="L1",
            zone_label="Lobby Atrium",
            name="Lobby Atrium North (demo file)",
            source_type="file",
            source_uri="/app/sample-data/input/first test video.mp4",
            input_format="mp4",
            credentials_ref=None,
            enabled=True,
            status="offline",
            health={},
            tags=["demo", "lobby"],
            position_notes="Demo source registered by seed data; footage from sample-data/input.",
            detection_config={"windowSeconds": 30, "sampleFramesPerWindow": 3, "minConfidence": 0.35},
            created_at=now,
            updated_at=now,
        ),
        # Placeholder RTSP source: honest 'adapter pending' state.
        SourceModel(
            id="src-demo-terrace",
            org_id=DEMO_ORG_ID,
            building_id="bldg-south-02",
            floor_id="flr-s02-l5",
            zone_id="zone-s02-terrace",
            floor_label="L5",
            zone_label="Terrace Entry",
            name="Terrace Exit (RTSP placeholder)",
            source_type="rtsp",
            source_uri="rtsp://replace-me/terrace",
            input_format="h264",
            credentials_ref="secret://demo/terrace-cam",
            enabled=False,
            status="offline",
            health={},
            tags=["demo", "placeholder"],
            position_notes="RTSP adapter is not implemented yet; source is disabled by default.",
            detection_config={},
            created_at=now,
            updated_at=now,
        ),
    ]
    session.add_all(sources)
    session.commit()
