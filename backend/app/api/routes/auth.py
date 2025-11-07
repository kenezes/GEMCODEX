from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import deps
from app.core.security import create_access_token, verify_password
from app.repositories.user import UserRepository
from app.schemas.auth import Token

router = APIRouter()

@router.post("/token", response_model=Token, summary="Obtain JWT access token")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), session: AsyncSession = Depends(deps.get_db)
) -> Token:
    repo = UserRepository(session)
    user = await repo.get_by_email(form_data.username)
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    expires_delta = timedelta(minutes=60)
    access_token = create_access_token(user.id, expires_delta=expires_delta)
    return Token(access_token=access_token, expires_at=datetime.utcnow() + expires_delta)
