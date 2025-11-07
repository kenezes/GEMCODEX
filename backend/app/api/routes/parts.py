from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.models import Part, Replacement
from app.schemas.common import PaginatedResponse
from app.schemas.parts import PartCreate, PartDetail, PartOut, PartUpdate, ReplacementLogEntry

router = APIRouter(prefix="/parts", tags=["parts"])

@router.get("/", response_model=PaginatedResponse[PartOut])
async def list_parts(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    search: Optional[str] = Query(None),
    session: AsyncSession = Depends(deps.get_db),
    _user=Depends(deps.get_current_user),
):
    stmt = select(Part)
    count_stmt = select(func.count()).select_from(Part)
    if search:
        condition = Part.name.ilike(f"%{search}%")
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)
    total_count = await session.scalar(count_stmt)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    items = result.scalars().all()
    return PaginatedResponse[PartOut](
        items=[PartOut.model_validate(item) for item in items],
        total=total_count or 0,
        page=page,
        page_size=page_size,
    )

@router.get("/{part_id}", response_model=PartDetail)
async def get_part(part_id: int, session: AsyncSession = Depends(deps.get_db), _user=Depends(deps.get_current_user)):
    part = await session.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    replacements = await session.execute(
        select(Replacement).where(Replacement.part_id == part_id).order_by(Replacement.date.desc())
    )
    replacement_items = [ReplacementLogEntry.model_validate(row) for row in replacements.scalars().all()]
    detail = PartDetail.model_validate(part)
    detail.replacements = replacement_items
    return detail

@router.post("/", response_model=PartOut, status_code=status.HTTP_201_CREATED)
async def create_part(
    payload: PartCreate,
    session: AsyncSession = Depends(deps.get_db),
    _user=Depends(deps.get_current_user),
):
    part = Part(**payload.model_dump())
    session.add(part)
    await session.commit()
    await session.refresh(part)
    return PartOut.model_validate(part)

@router.patch("/{part_id}", response_model=PartOut)
async def update_part(
    part_id: int,
    payload: PartUpdate,
    session: AsyncSession = Depends(deps.get_db),
    _user=Depends(deps.get_current_user),
):
    part = await session.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(part, key, value)
    await session.commit()
    await session.refresh(part)
    return PartOut.model_validate(part)

@router.delete("/{part_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_part(part_id: int, session: AsyncSession = Depends(deps.get_db), _user=Depends(deps.get_current_user)):
    part = await session.get(Part, part_id)
    if not part:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Part not found")
    await session.delete(part)
    await session.commit()
    return None
