import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, engine
from app.observability import install_observability
from app.request_limits import RequestSizeLimit
from app.routers import (
    auth,
    bootstrap,
    detections,
    evidence,
    incidents,
    live,
    org,
    pipeline,
    reports,
    sources,
    topology,
)
from app.seed import seed_database

settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.2.0")
app.add_middleware(RequestSizeLimit, max_bytes=settings.request_max_bytes)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_observability(app)

app.include_router(auth.router)
app.include_router(auth.users_router)
app.include_router(bootstrap.router)
app.include_router(topology.router)
app.include_router(sources.router)
app.include_router(live.router)
# Static stream path must precede /incidents/{incident_id}.
app.include_router(pipeline.router)
app.include_router(incidents.router)
app.include_router(detections.router)
app.include_router(evidence.router)
app.include_router(org.router)
app.include_router(reports.router)


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    service_root = Path(__file__).resolve().parents[1]
    config = Config(str(service_root / "alembic.ini"))
    config.set_main_option("script_location", str(service_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(config, "head")


@app.on_event("startup")
def startup() -> None:
    try:
        initialize_storage()
    except Exception:
        logging.getLogger(__name__).exception("API startup failed")
        raise


def initialize_storage() -> None:
    if settings.database_url.startswith("sqlite"):
        # Test/dev-lite mode: skip Alembic and build the schema directly.
        Base.metadata.create_all(bind=engine)
    else:
        run_migrations()

    if settings.seed_demo_data:
        with Session(engine) as session:
            seed_database(session)

    if settings.evidence_storage_enabled:
        try:
            from app.storage import ensure_bucket

            ensure_bucket()
        except Exception as exc:  # noqa: BLE001 - storage may lag behind the API.
            # Evidence uploads/presigns will 503 until MinIO is reachable.
            print(f"[api] evidence bucket not ready yet: {exc}", flush=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "api",
        "model_provider": settings.model_provider,
        "orchestrator": settings.orchestrator_name,
    }
