from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from config import settings
from database.models import Base

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # safe column additions for existing tables
        for sql in [
            "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS session_start VARCHAR(30)",
            "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS session_format VARCHAR(20)",
            "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS price NUMERIC(12,2)",
        ]:
            await conn.execute(__import__("sqlalchemy").text(sql))


async def get_session() -> AsyncSession:
    async with async_session_factory() as session:
        yield session
