from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps

router = APIRouter(prefix="/legacy", tags=["legacy"], deprecated=True)

class SQLRequest(BaseModel):
    query: str
    params: list[Any] | dict[str, Any] | None = None

class SQLResponse(BaseModel):
    rows: list[dict[str, Any]] | None = None
    rowcount: int | None = None
    lastrowid: int | None = None

ALLOWED_PREFIXES = ("select", "update", "delete", "insert", "with", "pragma")

@router.post("/sql", response_model=SQLResponse)
async def execute_sql(
    payload: SQLRequest,
    session: AsyncSession = Depends(deps.get_db),
    _user=Depends(deps.get_current_user),
) -> SQLResponse:
    statement = payload.query.strip()
    if not statement:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty query")
    lowered = statement.lower()
    if not lowered.startswith(ALLOWED_PREFIXES):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Statement not permitted")
    params = payload.params or {}
    result = await session.execute(text(statement), params)
    if lowered.startswith("select") or lowered.startswith("with"):
        rows = [dict(row._mapping) for row in result]
        return SQLResponse(rows=rows, rowcount=len(rows))
    await session.commit()
    lastrowid = getattr(result, "lastrowid", None)
    if not lastrowid and result.inserted_primary_key:
        try:
            lastrowid = int(result.inserted_primary_key[0])
        except (TypeError, ValueError, IndexError):
            lastrowid = None
    if lastrowid is None and lowered.startswith("insert"):
        try:
            lastrowid = await session.scalar(text("SELECT LASTVAL()"))
        except Exception:  # pragma: no cover - diagnostic only
            lastrowid = None
    return SQLResponse(rowcount=result.rowcount, lastrowid=lastrowid)
