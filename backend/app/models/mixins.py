from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
