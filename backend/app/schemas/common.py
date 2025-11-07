from datetime import datetime
from typing import Generic, Optional, Sequence, TypeVar

from pydantic import BaseModel

T = TypeVar("T")

class Timestamped(BaseModel):
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PaginatedResponse(BaseModel, Generic[T]):
    items: Sequence[T]
    total: int
    page: int
    page_size: int
