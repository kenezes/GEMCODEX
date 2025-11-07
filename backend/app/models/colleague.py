from __future__ import annotations

from typing import List, TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task

class Colleague(Base, TimestampMixin):
    __tablename__ = "colleagues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)

    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="assignee")
