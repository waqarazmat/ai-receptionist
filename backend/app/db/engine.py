from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def _to_async_dsn(dsn: str) -> str:
    """Ensure the DSN uses the asyncpg driver regardless of how it's written in .env."""
    if dsn.startswith("postgresql+asyncpg://"):
        return dsn
    if dsn.startswith("postgresql://"):
        return dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    return dsn


engine = create_async_engine(
    _to_async_dsn(settings.DATABASE_URL),
    pool_pre_ping=True,
    # Explicit but equal to SQLAlchemy's defaults (5 + 10 overflow, 30s wait) so
    # behavior is unchanged until tuned via env for multi-worker deployments.
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
