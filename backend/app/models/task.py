from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.colleague import Colleague
    from app.models.equipment import Equipment, EquipmentPart
    from app.models.part import Part

class Task(Base, TimestampMixin):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("priority IN ('низкий','средний','высокий')", name="ck_tasks_priority"),
        CheckConstraint("status IN ('в работе','выполнена','отменена','на стопе')", name="ck_tasks_status"),
        Index("ix_tasks_status_priority_due_date", "status", "priority", "due_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="средний")
    due_date: Mapped[date | None] = mapped_column(Date)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("colleagues.id", ondelete="SET NULL"))
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="в работе")
    is_replacement: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assignee: Mapped[Optional["Colleague"]] = relationship("Colleague", back_populates="tasks")
    equipment: Mapped[Optional["Equipment"]] = relationship("Equipment", back_populates="tasks")
    parts: Mapped[List["TaskPart"]] = relationship("TaskPart", back_populates="task", cascade="all, delete-orphan")

class TaskPart(Base, TimestampMixin):
    __tablename__ = "task_parts"
    __table_args__ = (
        Index("ix_task_parts_task_id", "task_id"),
        Index("ix_task_parts_equipment_part_id", "equipment_part_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    equipment_part_id: Mapped[int] = mapped_column(ForeignKey("equipment_parts.id", ondelete="CASCADE"))
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="RESTRICT"))
    qty: Mapped[int] = mapped_column(default=1)

    task: Mapped[Task] = relationship(back_populates="parts")
    equipment_part: Mapped["EquipmentPart"] = relationship("EquipmentPart", back_populates="task_parts")
    part: Mapped["Part"] = relationship("Part", back_populates="tasks")

class PeriodicTask(Base, TimestampMixin):
    __tablename__ = "periodic_tasks"
    __table_args__ = (
        Index("ix_periodic_tasks_due_idx", "period_days", "last_completed_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    equipment_id: Mapped[int | None] = mapped_column(ForeignKey("equipment.id", ondelete="SET NULL"))
    equipment_part_id: Mapped[int | None] = mapped_column(ForeignKey("equipment_parts.id", ondelete="SET NULL"))
    period_days: Mapped[int] = mapped_column(nullable=False)
    last_completed_date: Mapped[date | None] = mapped_column(Date)

    equipment: Mapped[Optional["Equipment"]] = relationship("Equipment")
    equipment_part: Mapped[Optional["EquipmentPart"]] = relationship("EquipmentPart")
