from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.equipment import EquipmentPart
    from app.models.knife import KnifeTracking
    from app.models.replacement import Replacement
    from app.models.task import TaskPart

class PartAnalogGroup(Base, TimestampMixin):
    __tablename__ = "part_analog_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    parts: Mapped[List["Part"]] = relationship(back_populates="analog_group")

class PartCategory(Base, TimestampMixin):
    __tablename__ = "part_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    parts: Mapped[List["Part"]] = relationship(back_populates="category")

class Part(Base, TimestampMixin):
    __tablename__ = "parts"
    __table_args__ = (
        UniqueConstraint("name", "sku", name="uq_parts_name_sku"),
        Index("ix_parts_category_id", "category_id"),
        Index("ix_parts_analog_group_id", "analog_group_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str] = mapped_column(String(255), nullable=False)
    qty: Mapped[int] = mapped_column(default=0)
    min_qty: Mapped[int] = mapped_column(default=0)
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("part_categories.id", ondelete="SET NULL"))
    analog_group_id: Mapped[int | None] = mapped_column(ForeignKey("part_analog_groups.id", ondelete="SET NULL"))

    category: Mapped[Optional[PartCategory]] = relationship(back_populates="parts")
    analog_group: Mapped[Optional[PartAnalogGroup]] = relationship(back_populates="parts")
    equipment_parts: Mapped[List["EquipmentPart"]] = relationship("EquipmentPart", back_populates="part")
    replacements: Mapped[List["Replacement"]] = relationship("Replacement", back_populates="part")
    tasks: Mapped[List["TaskPart"]] = relationship("TaskPart", back_populates="part")
    knife_tracking: Mapped[Optional["KnifeTracking"]] = relationship("KnifeTracking", back_populates="part", uselist=False)
