from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.part import Part

class Replacement(Base, TimestampMixin):
    __tablename__ = "replacements"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.id", ondelete="RESTRICT"))
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="RESTRICT"))
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reason: Mapped[str | None] = mapped_column(Text)

    equipment: Mapped["Equipment"] = relationship("Equipment")
    part: Mapped["Part"] = relationship("Part", back_populates="replacements")
