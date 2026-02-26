from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base


engine = None
session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(database_url: str) -> None:
    global engine, session_factory
    engine = create_async_engine(database_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def create_tables() -> None:
    if engine is None:
        raise RuntimeError("Database engine is not initialized.")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if session_factory is None:
        raise RuntimeError("Session factory is not initialized.")
    async with session_factory() as session:
        yield session
