"""Release step: `python -m app.migrate` applies database migrations and exits.

Production sets SMARTOPS_RUN_MIGRATIONS_ON_STARTUP=false so API replicas never
race each other on schema changes; this command runs once per release.
"""
import logging
import sys

from app.main import run_migrations, schema_revision_status


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    before, head = schema_revision_status()
    run_migrations()
    after, _ = schema_revision_status()
    print(f"Database migrated: {before or 'empty'} -> {after} (head {head})")
    return 0 if after == head else 1


if __name__ == "__main__":
    sys.exit(main())
