from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

INCIDENT_STATUSES = (
    "active",
    "acknowledged",
    "assigned",
    "in_progress",
    "resolved",
    "false_positive",
    "escalated",
    "human_review",
)

INCIDENT_CATEGORIES = (
    "Safety",
    "Housekeeping",
    "Occupancy",
    "Security",
    "Queue & Crowd",
    "System Health",
)


class IncidentModel(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    subcategory: Mapped[str | None] = mapped_column(String(80), nullable=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    building_id: Mapped[str] = mapped_column(String(80), nullable=False)
    floor: Mapped[str] = mapped_column(String(32), nullable=False)
    zone: Mapped[str] = mapped_column(String(120), nullable=False)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    candidate_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ack_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    short_summary: Mapped[str] = mapped_column(String(240), nullable=False)
    detailed_narrative: Mapped[list] = mapped_column(JSON, nullable=False)
    recommended_actions: Mapped[list] = mapped_column(JSON, nullable=False)
    review_notes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # Legacy direct URLs kept until object-storage evidence fully replaces
    # them; evidence_items is the canonical linkage.
    evidence_thumbnail_url: Mapped[str] = mapped_column(String(240), nullable=False)
    evidence_clip_url: Mapped[str] = mapped_column(String(240), nullable=False)
    evidence_restricted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    assigned_to: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model_version: Mapped[str] = mapped_column(String(120), nullable=False)
    # Summary of the detector output that gated this incident, e.g.
    # {"personCount": 4, "labels": {"person": 4}, "detectionIds": [...]}.
    detection_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    events: Mapped[list["IncidentEventModel"]] = relationship(  # noqa: F821
        back_populates="incident", cascade="all, delete-orphan", order_by="IncidentEventModel.created_at"
    )
    comments: Mapped[list["IncidentCommentModel"]] = relationship(  # noqa: F821
        back_populates="incident", cascade="all, delete-orphan", order_by="IncidentCommentModel.created_at"
    )
    evidence_items: Mapped[list["EvidenceItemModel"]] = relationship(  # noqa: F821
        back_populates="incident", order_by="EvidenceItemModel.created_at"
    )
