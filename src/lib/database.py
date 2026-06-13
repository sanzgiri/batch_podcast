"""Database configuration and session management for Newsletter Podcast Generator."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.lib.config import get_config


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all models."""
    pass


# Module-level engine and session factory (initialized lazily)
_engine = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _get_engine():
    """Get or create the async engine."""
    global _engine
    if _engine is None:
        config = get_config()
        db_url = config.database.url

        # Ensure parent directory exists for SQLite
        if "sqlite" in db_url:
            # Extract path from URL like sqlite+aiosqlite:///./data/foo.db
            db_path_str = db_url.split("///")[-1]
            db_path = Path(db_path_str)
            db_path.parent.mkdir(parents=True, exist_ok=True)

        connect_args = {}
        if "sqlite" in db_url:
            connect_args["check_same_thread"] = False

        _engine = create_async_engine(
            db_url,
            echo=config.database.echo,
            connect_args=connect_args,
        )
    return _engine


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def init_database() -> None:
    """Initialize database tables."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database sessions."""
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
