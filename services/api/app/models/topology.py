from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class BuildingModel(Base):
    __tablename__ = "buildings"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str] = mapped_column(String(160), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)

    floors: Mapped[list["FloorModel"]] = relationship(
        back_populates="building", cascade="all, delete-orphan", order_by="FloorModel.level"
    )


class FloorModel(Base):
    __tablename__ = "floors"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    building_id: Mapped[str] = mapped_column(ForeignKey("buildings.id"), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    building: Mapped["BuildingModel"] = relationship(back_populates="floors")
    zones: Mapped[list["ZoneModel"]] = relationship(
        back_populates="floor", cascade="all, delete-orphan", order_by="ZoneModel.name"
    )


class ZoneModel(Base):
    __tablename__ = "zones"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    floor_id: Mapped[str] = mapped_column(ForeignKey("floors.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    # kind distinguishes open zones from enclosed rooms without a second table.
    kind: Mapped[str] = mapped_column(String(32), default="zone", nullable=False)

    floor: Mapped["FloorModel"] = relationship(back_populates="zones")
