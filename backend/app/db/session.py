from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

class Base(DeclarativeBase):
    pass

_settings = get_settings()
DATABASE_URL = (
    f"postgresql+asyncpg://{_settings.postgres_user}:{_settings.postgres_password}"
    f"@{_settings.postgres_host}:{_settings.postgres_port}/{_settings.postgres_db}"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
