from __future__ import annotations

from typing import List, TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.order import Order

class Counterparty(Base, TimestampMixin):
    __tablename__ = "counterparties"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    address: Mapped[str | None] = mapped_column()
    contact_person: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str | None] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column()
    driver_note: Mapped[str | None] = mapped_column()

    orders: Mapped[List["Order"]] = relationship("Order", back_populates="counterparty")
    addresses: Mapped[List["CounterpartyAddress"]] = relationship("CounterpartyAddress", back_populates="counterparty", cascade="all, delete-orphan")

class CounterpartyAddress(Base, TimestampMixin):
    __tablename__ = "counterparty_addresses"
    __table_args__ = (
        Index("ix_counterparty_addresses_counterparty_id", "counterparty_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    counterparty_id: Mapped[int] = mapped_column(ForeignKey("counterparties.id", ondelete="CASCADE"))
    address: Mapped[str] = mapped_column()
    is_default: Mapped[bool] = mapped_column(default=False)

    counterparty: Mapped[Counterparty] = relationship(back_populates="addresses")
