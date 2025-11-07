from __future__ import annotations

from datetime import date, datetime
from typing import List, TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.part import Part

class KnifeTracking(Base, TimestampMixin):
    __tablename__ = "knife_tracking"
    __table_args__ = (
        CheckConstraint("status IN ('в работе','наточен','затуплен')", name="ck_knife_tracking_status"),
        CheckConstraint("sharp_state IN ('заточен','затуплен')", name="ck_knife_tracking_sharp_state"),
        CheckConstraint("installation_state IN ('установлен','снят')", name="ck_knife_tracking_installation_state"),
        Index("ix_knife_tracking_status", "status"),
    )

    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id", ondelete="RESTRICT"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="наточен")
    sharp_state: Mapped[str] = mapped_column(String(20), nullable=False, default="заточен")
    installation_state: Mapped[str] = mapped_column(String(20), nullable=False, default="снят")
    last_sharpen_date: Mapped[date | None] = mapped_column(Date)
    work_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_interval_days: Mapped[int | None] = mapped_column(Integer)
    total_sharpenings: Mapped[int] = mapped_column(default=0)

    part: Mapped["Part"] = relationship("Part", back_populates="knife_tracking")
    status_log: Mapped[List["KnifeStatusLog"]] = relationship("KnifeStatusLog", back_populates="knife", cascade="all, delete-orphan")
    sharpen_log: Mapped[List["KnifeSharpenLog"]] = relationship("KnifeSharpenLog", back_populates="knife", cascade="all, delete-orphan")

class KnifeStatusLog(Base, TimestampMixin):
    __tablename__ = "knife_status_log"
    __table_args__ = (
        Index("ix_knife_status_log_part_id", "part_id", "changed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("knife_tracking.part_id", ondelete="CASCADE"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    knife: Mapped[KnifeTracking] = relationship(back_populates="status_log")

class KnifeSharpenLog(Base, TimestampMixin):
    __tablename__ = "knife_sharpen_log"
    __table_args__ = (
        Index("ix_knife_sharpen_log_part_id", "part_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("knife_tracking.part_id", ondelete="CASCADE"))
    date: Mapped[date] = mapped_column(Date, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    knife: Mapped[KnifeTracking] = relationship(back_populates="sharpen_log")
