"""Local demo seed: three client-type workspaces.

Everything created here is demo scaffolding for a local laptop: three
organizations (an office tower, a shopping mall and a campus), one user per
role in each (shared demo password), building topology and cameras.

Cameras are RTSP sources on mediamtx paths. A camera is enabled only when
`sample-data/streams.json` says footage is published to its path; the others
stay disabled with a note saying what they are waiting for. Incidents are
never seeded. They come only from the real pipeline running over the streams.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BuildingModel, FloorModel, OrganizationModel, SourceModel, UserModel, ZoneModel
from app.security import hash_password

DEMO_ORG_ID = "org-demo"
DEMO_PASSWORD = "smartops-demo"
RTSP_BASE = "rtsp://mediamtx:8554"

ROLES = [("admin", "Avery Admin"), ("supervisor", "Sam Supervisor"), ("operator", "Olivia Operator"),
         ("viewer", "Vik Viewer"), ("security", "Selin Security"), ("ehs", "Eli EHS")]

# Detection zones use normalized image coordinates; the anchor of each person
# is the bottom-centre of the box (where the feet touch the floor).
MALL_STORE_ZONES = [
    {"id": "Checkout queue",
     "polygon": [[0.0, 0.3], [0.33, 0.3], [0.33, 1.0], [0.0, 1.0]],
     "rules": [{"type": "queue_build_up", "threshold": 1, "durationSeconds": 8}]},
    {"id": "Front aisle",
     "polygon": [[0.45, 0.45], [1.0, 0.45], [1.0, 1.0], [0.45, 1.0]],
     "rules": [{"type": "crowding", "threshold": 2, "durationSeconds": 5}]},
    {"id": "Promo display",
     "polygon": [[0.33, 0.5], [0.45, 0.5], [0.45, 1.0], [0.33, 1.0]],
     "rules": [{"type": "loitering", "durationSeconds": 20}]},
]

OFFICE_LOBBY_ZONES = [
    {"id": "Restricted wing",
     "polygon": [[0.52, 0.30], [0.76, 0.30], [0.76, 0.46], [0.52, 0.46]],
     "rules": [{"type": "restricted_entry", "durationSeconds": 0, "cooldownSeconds": 60}]},
    {"id": "Lobby floor",
     "polygon": [[0.30, 0.30], [0.78, 0.30], [0.78, 0.95], [0.30, 0.95]],
     "rules": [{"type": "crowding", "threshold": 3, "durationSeconds": 3}]},
]

MALL_ATRIUM_ZONES = [
    {"id": "Atrium floor",
     "polygon": [[0.35, 0.30], [1.0, 0.30], [1.0, 1.0], [0.35, 1.0]],
     "rules": [{"type": "crowding", "threshold": 5, "durationSeconds": 5}]},
]

CAMPUS_LAB_ZONES = [
    {"id": "Lab entrance steps",
     "polygon": [[0.0, 0.50], [0.80, 0.50], [0.80, 1.0], [0.0, 1.0]],
     "rules": [{"type": "restricted_entry", "durationSeconds": 1, "cooldownSeconds": 120}]},
]

WORKSPACES = [
    {
        "id": DEMO_ORG_ID, "name": "Northpoint Office Tower", "slug": "northpoint-office",
        "accent": "#38bdf8", "email": lambda role: f"{role}@smartops.local", "user_prefix": "usr",
        "buildings": [
            {"id": "bldg-north-01", "name": "Northpoint Tower", "address": "200 Market Plaza",
             "floors": [
                 {"id": "flr-n01-l1", "level": "L1", "name": "Ground Lobby",
                  "zones": [("zone-n01-atrium", "Lobby Atrium"), ("zone-n01-elev", "Elevator Bank")]},
                 {"id": "flr-n01-l2", "level": "L2", "name": "Amenities",
                  "zones": [("zone-n01-pantry", "Pantry & Cafe"), ("zone-n01-server", "Server Room Corridor")]},
             ]},
            {"id": "bldg-south-02", "name": "Harbor View Annex", "address": "88 Bay Street",
             "floors": [
                 {"id": "flr-s02-l1", "level": "L1", "name": "Entrance",
                  "zones": [("zone-s02-entry", "Main Entry"), ("zone-s02-exit", "Fire Exit East")]},
             ]},
        ],
        "cameras": [
            {"id": "src-office-lobby", "name": "Lobby turnstiles", "building": "bldg-north-01",
             "floor": "flr-n01-l1", "zone": "zone-n01-atrium", "path": "office-lobby",
             "zones": OFFICE_LOBBY_ZONES},
            {"id": "src-office-server", "name": "Server room corridor", "building": "bldg-north-01",
             "floor": "flr-n01-l2", "zone": "zone-n01-server", "path": "office-server-room"},
            {"id": "src-office-exit", "name": "Fire exit east", "building": "bldg-south-02",
             "floor": "flr-s02-l1", "zone": "zone-s02-exit", "path": "office-fire-exit"},
        ],
    },
    {
        "id": "org-mall", "name": "Harborline Mall", "slug": "harborline-mall",
        "accent": "#f472b6", "email": lambda role: f"{role}@mall.demo", "user_prefix": "usr-mall",
        "buildings": [
            {"id": "bldg-mall-01", "name": "Harborline Mall", "address": "1 Harbor Road",
             "floors": [
                 {"id": "flr-mall-g", "level": "G", "name": "Ground Retail",
                  "zones": [("zone-mall-store", "Convenience Store"), ("zone-mall-atrium", "Central Atrium")]},
                 {"id": "flr-mall-2", "level": "L2", "name": "Food Court",
                  "zones": [("zone-mall-food", "Food Court Queue")]},
             ]},
        ],
        "cameras": [
            {"id": "src-mall-store", "name": "Convenience store floor", "building": "bldg-mall-01",
             "floor": "flr-mall-g", "zone": "zone-mall-store", "path": "mall-store",
             "zones": MALL_STORE_ZONES},
            {"id": "src-mall-atrium", "name": "Central atrium", "building": "bldg-mall-01",
             "floor": "flr-mall-g", "zone": "zone-mall-atrium", "path": "mall-atrium",
             "zones": MALL_ATRIUM_ZONES},
            {"id": "src-mall-food", "name": "Food court queue", "building": "bldg-mall-01",
             "floor": "flr-mall-2", "zone": "zone-mall-food", "path": "mall-food-court"},
        ],
    },
    {
        "id": "org-campus", "name": "Riverside Campus", "slug": "riverside-campus",
        "accent": "#a3e635", "email": lambda role: f"{role}@campus.demo", "user_prefix": "usr-campus",
        "buildings": [
            {"id": "bldg-campus-lib", "name": "Library", "address": "Riverside Campus, Block A",
             "floors": [
                 {"id": "flr-campus-lib-g", "level": "G", "name": "Reading Hall",
                  "zones": [("zone-campus-benches", "Entrance Benches"), ("zone-campus-lab", "Restricted Lab")]},
             ]},
        ],
        "cameras": [
            {"id": "src-campus-benches", "name": "Library entrance benches", "building": "bldg-campus-lib",
             "floor": "flr-campus-lib-g", "zone": "zone-campus-benches", "path": "campus-benches"},
            {"id": "src-campus-lab", "name": "Restricted lab door", "building": "bldg-campus-lib",
             "floor": "flr-campus-lib-g", "zone": "zone-campus-lab", "path": "campus-lab",
             "zones": CAMPUS_LAB_ZONES},
        ],
    },
]


def published_paths() -> dict[str, str]:
    """mediamtx path -> footage file, from the publisher manifest (if mounted)."""
    import json
    from pathlib import Path

    from app.config import get_settings

    manifest = Path(get_settings().source_root).parent / "streams.json"
    try:
        entries = json.loads(manifest.read_text(encoding="utf-8")).get("streams", [])
    except (OSError, ValueError):
        return {}
    return {str(entry["path"]): str(entry["file"]) for entry in entries if entry.get("path") and entry.get("file")}


def seed_database(session: Session) -> None:
    existing_orgs = session.scalar(select(func.count(OrganizationModel.id)))
    if existing_orgs and existing_orgs > 0:
        return
    seed_workspaces(session, published_paths())


def seed_workspaces(session: Session, publishing: dict[str, str]) -> None:
    now = datetime.now(UTC)
    password_hash = hash_password(DEMO_PASSWORD)  # one demo password for every seeded account
    for workspace in WORKSPACES:
        org_id = workspace["id"]
        session.add(OrganizationModel(id=org_id, name=workspace["name"], slug=workspace["slug"],
                                      settings={"accent": workspace["accent"]}, created_at=now))
        session.flush()
        for role, person in ROLES:
            session.add(UserModel(
                id=f"{workspace['user_prefix']}-{role}", org_id=org_id, email=workspace["email"](role),
                name=person, password_hash=password_hash, role=role,
                active=True, created_at=now,
            ))
        zone_names: dict[str, tuple[str, str]] = {}
        for building in workspace["buildings"]:
            session.add(BuildingModel(id=building["id"], org_id=org_id, name=building["name"],
                                      address=building["address"], timezone="Asia/Kolkata"))
            session.flush()
            for floor in building["floors"]:
                session.add(FloorModel(id=floor["id"], building_id=building["id"], level=floor["level"],
                                       name=floor["name"]))
                session.flush()
                for zone_id, zone_name in floor["zones"]:
                    session.add(ZoneModel(id=zone_id, floor_id=floor["id"], name=zone_name, kind="zone"))
                    zone_names[zone_id] = (floor["level"], zone_name)
        session.flush()
        for camera in workspace["cameras"]:
            level, zone_name = zone_names[camera["zone"]]
            footage = publishing.get(camera["path"])
            uri = f"{RTSP_BASE}/{camera['path']}"
            if footage:
                note = f"Looping recorded footage '{footage}' published by stream-publisher."
            else:
                note = (f"No footage assigned yet. Publish a stream to {uri} (or connect a phone/IP camera) "
                        "and enable this camera.")
            session.add(SourceModel(
                id=camera["id"], org_id=org_id, building_id=camera["building"], floor_id=camera["floor"],
                zone_id=camera["zone"], floor_label=level, zone_label=zone_name, name=camera["name"],
                source_type="rtsp", source_uri=uri, input_format="h264", credentials_ref=None,
                enabled=bool(footage), status="offline", health={},
                tags=["demo", "recorded-loop" if footage else "awaiting-footage"],
                position_notes=note,
                detection_config={"zones": camera.get("zones", [])} if camera.get("zones") else {},
                created_at=now, updated_at=now,
            ))
        session.flush()
    session.commit()
