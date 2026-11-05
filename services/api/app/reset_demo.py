"""Return the local demo to a freshly seeded state: `python -m app.reset_demo`.

Deletes every row in every SmartOps table (one TRUNCATE on PostgreSQL),
reseeds the three demo workspaces and empties the evidence bucket. Refuses
to run when SMARTOPS_ENVIRONMENT=production. The stream processor's local
journals are cleared separately by demo.ps1 while the processor is stopped.
"""

from __future__ import annotations

import sys
import time

from sqlalchemy import text

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.seed import published_paths, seed_workspaces


def clear_database() -> None:
    tables = [table.name for table in reversed(Base.metadata.sorted_tables)]
    with engine.begin() as connection:
        if engine.dialect.name == "postgresql":
            quoted = ", ".join(f'"{name}"' for name in tables)
            connection.execute(text(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE"))
        else:
            for name in tables:
                connection.execute(text(f'DELETE FROM "{name}"'))


def clear_evidence() -> int:
    settings = get_settings()
    if not settings.evidence_storage_enabled:
        return 0
    from minio.deleteobjects import DeleteObject

    from app.storage import ensure_bucket, internal_client

    ensure_bucket()
    client = internal_client()
    objects = [DeleteObject(item.object_name)
               for item in client.list_objects(settings.minio_bucket, recursive=True)]
    errors = list(client.remove_objects(settings.minio_bucket, objects)) if objects else []
    if errors:
        raise RuntimeError(f"Could not delete {len(errors)} evidence objects")
    return len(objects)


def main() -> int:
    settings = get_settings()
    if settings.environment.strip().lower() == "production":
        print("Refusing to reset: SMARTOPS_ENVIRONMENT=production", file=sys.stderr)
        return 2
    started = time.perf_counter()
    clear_database()
    removed = clear_evidence()
    with SessionLocal() as session:
        seed_workspaces(session, published_paths())
    print(f"Demo reset: database reseeded, {removed} evidence objects removed "
          f"in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
