from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

EVIDENCE_KINDS = ("snapshot", "thumbnail", "clip", "metadata")


class EvidenceAccessModel(Base):
    """Records URL issuance, not proof that the recipient downloaded an object."""

    __tablename__ = 'evidence_access'
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey('organizations.id'), nullable=False, index=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey('evidence_items.id'), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class EvidenceItemModel(Base):
    """Object-storage-backed evidence artifact (MinIO/S3).

    object_key points into the evidence bucket; the API issues short-lived
    presigned URLs instead of exposing raw storage paths.
    """

    __tablename__ = "evidence_items"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"), nullable=True, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    candidate_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    object_key: Mapped[str] = mapped_column(String(320), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    restricted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    incident: Mapped["IncidentModel | None"] = relationship(back_populates="evidence_items")  # noqa: F821
