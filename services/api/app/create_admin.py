"""Create the first workspace and its admin on a fresh deployment.

Production refuses demo seeding, so a new install needs one explicit admin:

    docker compose ... run --rm -e SMARTOPS_ADMIN_PASSWORD=... api \
        python -m app.create_admin --workspace "Acme Facilities" --email ops@acme.example

The password comes from the SMARTOPS_ADMIN_PASSWORD environment variable
(never a command-line argument, which would land in shell history). Running
it again for an existing email changes nothing and says so.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import UTC, datetime

from sqlalchemy import select

from app.db import SessionLocal
from app.ids import new_id
from app.models import OrganizationModel, UserModel
from app.security import hash_password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Workspace Admin")
    args = parser.parse_args(argv)
    password = os.environ.get("SMARTOPS_ADMIN_PASSWORD", "")
    if len(password) < 12:
        print("Set SMARTOPS_ADMIN_PASSWORD (at least 12 characters).", file=sys.stderr)
        return 2
    email = args.email.strip().lower()
    with SessionLocal() as session:
        if session.scalar(select(UserModel.id).where(UserModel.email == email)):
            print(f"{email} already exists; nothing changed.")
            return 0
        slug = re.sub(r"[^a-z0-9]+", "-", args.workspace.lower()).strip("-")[:40] or "workspace"
        org = session.scalar(select(OrganizationModel).where(OrganizationModel.slug == slug))
        now = datetime.now(UTC)
        if org is None:
            org = OrganizationModel(id=f"org-{slug}", name=args.workspace.strip(), slug=slug, settings={},
                                    created_at=now)
            session.add(org)
            session.flush()
        session.add(UserModel(id=new_id("usr"), org_id=org.id, email=email, name=args.name, role="admin",
                              password_hash=hash_password(password), active=True, created_at=now))
        session.commit()
        print(f"Created admin {email} in workspace '{org.name}' ({org.id}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
