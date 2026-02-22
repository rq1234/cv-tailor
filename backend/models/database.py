from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings

DATABASE_URL = get_settings().database_url

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # Keep pool small — Supabase free tier caps total connections at ~60 via pgbouncer.
    pool_size=5,
    max_overflow=5,
    # Validate connections before use; drops stale connections from the pool.
    pool_pre_ping=True,
    # Recycle connections after 30 min to avoid silent server-side timeouts.
    pool_recycle=1800,
    # Raise immediately if no connection is available within 30 s.
    pool_timeout=30,
    # Supabase transaction pooler doesn't support PREPARE statements.
    connect_args={"statement_cache_size": 0, "prepared_statement_cache_size": 0},
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session() as session:
        yield session
