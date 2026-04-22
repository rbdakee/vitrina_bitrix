from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings


class DatabaseRuntime:
    def __init__(self, settings: Settings) -> None:
        self.engine: AsyncEngine = create_async_engine(
            settings.sqlalchemy_database_url,
            echo=False,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    async def dispose(self) -> None:
        await self.engine.dispose()


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
