from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

SOURCE_TYPES = ("file", "rtsp", "onvif", "webrtc")
SOURCE_STATUSES = ("online", "offline", "paused", "failing", "processing")


class SourceModel(Base):
    """A registered CCTV/video input.

    floor_label/zone_label are denormalized display strings so ingestion and
    incidents keep working even when a source is not linked to structured
    floor/zone rows yet. floor_id/zone_id are the structured linkage.
    """

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    building_id: Mapped[str] = mapped_column(ForeignKey("buildings.id"), nullable=False)
    floor_id: Mapped[str | None] = mapped_column(ForeignKey("floors.id"), nullable=True)
    zone_id: Mapped[str | None] = mapped_column(ForeignKey("zones.id"), nullable=True)
    floor_label: Mapped[str] = mapped_column(String(32), nullable=False)
    zone_label: Mapped[str] = mapped_column(String(120), nullable=False)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    input_format: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Placeholder reference to a secrets-manager entry; raw credentials are
    # never stored in this table.
    credentials_ref: Mapped[str | None] = mapped_column(String(160), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="offline", nullable=False)
    health: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    position_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    detection_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    building: Mapped["BuildingModel"] = relationship()  # noqa: F821 - resolved via registry
    floor: Mapped["FloorModel | None"] = relationship()  # noqa: F821
    zone: Mapped["ZoneModel | None"] = relationship()  # noqa: F821
