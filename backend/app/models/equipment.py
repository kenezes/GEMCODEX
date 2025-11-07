from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.part import Part
    from app.models.task import Task, TaskPart

class EquipmentCategory(Base, TimestampMixin):
    __tablename__ = "equipment_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    equipment: Mapped[List["Equipment"]] = relationship(back_populates="category")

class Equipment(Base, TimestampMixin):
    __tablename__ = "equipment"
    __table_args__ = (
        UniqueConstraint("name", name="uq_equipment_name"),
        Index("ix_equipment_category_id", "category_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(255))
    category_id: Mapped[int] = mapped_column(ForeignKey("equipment_categories.id", ondelete="RESTRICT"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"))
    comment: Mapped[str | None] = mapped_column()

    category: Mapped[EquipmentCategory] = relationship(back_populates="equipment")
    parent: Mapped[Optional["Equipment"]] = relationship(remote_side="Equipment.id", back_populates="children")
    children: Mapped[List["Equipment"]] = relationship(back_populates="parent")
    equipment_parts: Mapped[List["EquipmentPart"]] = relationship(back_populates="equipment")
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="equipment")

class EquipmentPart(Base, TimestampMixin):
    __tablename__ = "equipment_parts"
    __table_args__ = (
        UniqueConstraint("equipment_id", "part_id", name="uq_equipment_parts_equipment_part"),
        Index("ix_equipment_parts_part_id", "part_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="RESTRICT"))
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="RESTRICT"))
    installed_qty: Mapped[int] = mapped_column(default=1)
    comment: Mapped[str | None] = mapped_column()
    last_replacement_override: Mapped[str | None] = mapped_column()
    requires_replacement: Mapped[bool] = mapped_column(default=False)

    equipment: Mapped[Equipment] = relationship(back_populates="equipment_parts")
    part: Mapped["Part"] = relationship("Part", back_populates="equipment_parts")
    complex_component: Mapped[Optional["ComplexComponent"]] = relationship("ComplexComponent", back_populates="equipment_part", uselist=False)
    task_parts: Mapped[List["TaskPart"]] = relationship("TaskPart", back_populates="equipment_part")

class ComplexComponent(Base, TimestampMixin):
    __tablename__ = "complex_components"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_part_id: Mapped[int] = mapped_column(ForeignKey("equipment_parts.id", ondelete="CASCADE"), unique=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="CASCADE"), unique=True)

    equipment_part: Mapped[EquipmentPart] = relationship(back_populates="complex_component")
    equipment: Mapped[Equipment] = relationship()
