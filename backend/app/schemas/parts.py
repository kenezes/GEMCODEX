from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import Timestamped

class PartCategoryCreate(BaseModel):
    name: str

class PartCategoryOut(Timestamped):
    id: int
    name: str

    class Config:
        from_attributes = True

class PartBase(BaseModel):
    name: str
    sku: str
    qty: int = 0
    min_qty: int = 0
    price: float = 0
    category_id: Optional[int] = Field(default=None)
    analog_group_id: Optional[int] = Field(default=None)

class PartCreate(PartBase):
    pass

class PartUpdate(BaseModel):
    name: Optional[str]
    sku: Optional[str]
    qty: Optional[int]
    min_qty: Optional[int]
    price: Optional[float]
    category_id: Optional[int]
    analog_group_id: Optional[int]

class PartOut(Timestamped):
    id: int
    name: str
    sku: str
    qty: int
    min_qty: int
    price: float
    category_id: Optional[int]
    analog_group_id: Optional[int]

    class Config:
        from_attributes = True

class ReplacementLogEntry(BaseModel):
    id: int
    date: date
    equipment_id: int
    part_id: int
    qty: int
    reason: Optional[str]

    class Config:
        from_attributes = True

class PartDetail(PartOut):
    replacements: List[ReplacementLogEntry] = []
