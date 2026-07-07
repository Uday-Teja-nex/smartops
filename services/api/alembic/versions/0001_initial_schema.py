"""Initial SaaS-shaped schema.

Drops the pre-Alembic demo tables (created by the old create_all startup
path) if they exist — those held only local demo/seed data — and creates the
full multi-tenant schema.

Revision ID: 0001
Revises:
Create Date: 2026-07-06

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

LEGACY_TABLES = ("incidents", "cameras", "buildings")


def upgrade() -> None:
    # Remove pre-Alembic demo tables so this migration is deterministic on
    # dev machines that ran the old create_all schema.
    for table in LEGACY_TABLES:
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))

    op.create_table(
        "organizations",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("org_id", sa.String(80), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("email", sa.String(160), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("password_hash", sa.String(320), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "buildings",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("org_id", sa.String(80), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("address", sa.String(160), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
    )

    op.create_table(
        "floors",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("building_id", sa.String(80), sa.ForeignKey("buildings.id"), nullable=False),
        sa.Column("level", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
    )

    op.create_table(
        "zones",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("floor_id", sa.String(80), sa.ForeignKey("floors.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("org_id", sa.String(80), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("building_id", sa.String(80), sa.ForeignKey("buildings.id"), nullable=False),
        sa.Column("floor_id", sa.String(80), sa.ForeignKey("floors.id"), nullable=True),
        sa.Column("zone_id", sa.String(80), sa.ForeignKey("zones.id"), nullable=True),
        sa.Column("floor_label", sa.String(32), nullable=False),
        sa.Column("zone_label", sa.String(120), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_uri", sa.Text(), nullable=False),
        sa.Column("input_format", sa.String(32), nullable=True),
        sa.Column("credentials_ref", sa.String(160), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("health", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("position_notes", sa.Text(), nullable=True),
        sa.Column("detection_config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "incidents",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("org_id", sa.String(80), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("subcategory", sa.String(80), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("building_id", sa.String(80), nullable=False),
        sa.Column("floor", sa.String(32), nullable=False),
        sa.Column("zone", sa.String(120), nullable=False),
        sa.Column("source_id", sa.String(80), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("candidate_id", sa.String(160), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ack_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sla_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("short_summary", sa.String(240), nullable=False),
        sa.Column("detailed_narrative", sa.JSON(), nullable=False),
        sa.Column("recommended_actions", sa.JSON(), nullable=False),
        sa.Column("review_notes", sa.JSON(), nullable=False),
        sa.Column("evidence_thumbnail_url", sa.String(240), nullable=False),
        sa.Column("evidence_clip_url", sa.String(240), nullable=False),
        sa.Column("evidence_restricted", sa.Boolean(), nullable=False),
        sa.Column("assigned_to", sa.String(120), nullable=True),
        sa.Column("model_provider", sa.String(80), nullable=False),
        sa.Column("model_version", sa.String(120), nullable=False),
        sa.Column("detection_summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incidents_status", "incidents", ["status"])
    op.create_index("ix_incidents_source_id", "incidents", ["source_id"])
    op.create_index("ix_incidents_candidate_id", "incidents", ["candidate_id"])

    op.create_table(
        "detections",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("org_id", sa.String(80), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("source_id", sa.String(80), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("candidate_id", sa.String(160), nullable=False),
        sa.Column("label", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("bbox_x", sa.Float(), nullable=False),
        sa.Column("bbox_y", sa.Float(), nullable=False),
        sa.Column("bbox_w", sa.Float(), nullable=False),
        sa.Column("bbox_h", sa.Float(), nullable=False),
        sa.Column("frame_ts", sa.Float(), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_detections_source_id", "detections", ["source_id"])
    op.create_index("ix_detections_candidate_id", "detections", ["candidate_id"])

    op.create_table(
        "incident_events",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("incident_id", sa.String(80), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("actor", sa.String(160), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("from_status", sa.String(32), nullable=True),
        sa.Column("to_status", sa.String(32), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incident_events_incident_id", "incident_events", ["incident_id"])

    op.create_table(
        "incident_comments",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("incident_id", sa.String(80), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("author", sa.String(160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incident_comments_incident_id", "incident_comments", ["incident_id"])

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("org_id", sa.String(80), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("incident_id", sa.String(80), sa.ForeignKey("incidents.id"), nullable=True),
        sa.Column("source_id", sa.String(80), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("candidate_id", sa.String(160), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("object_key", sa.String(320), nullable=False),
        sa.Column("content_type", sa.String(80), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("restricted", sa.Boolean(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_items_incident_id", "evidence_items", ["incident_id"])
    op.create_index("ix_evidence_items_source_id", "evidence_items", ["source_id"])
    op.create_index("ix_evidence_items_candidate_id", "evidence_items", ["candidate_id"])


def downgrade() -> None:
    for table in (
        "evidence_items",
        "incident_comments",
        "incident_events",
        "detections",
        "incidents",
        "sources",
        "zones",
        "floors",
        "buildings",
        "users",
        "organizations",
    ):
        op.drop_table(table)
