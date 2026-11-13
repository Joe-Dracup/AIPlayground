import asyncio

import pytest
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db import Base
from app.main import app
from app.store import PostgresConversationStore, get_store

# Same server as the app, separate database, so tests never touch dev data.
TEST_DATABASE_URL = make_url(settings.database_url).set(database="aiplayground_test")


def make_engine(url=TEST_DATABASE_URL, **kwargs):
    # NullPool: no connections kept between uses. The tests and the app under test run on
    # different event loops, and an asyncpg connection only works on the loop that opened it.
    return create_async_engine(url, poolclass=NullPool, **kwargs)


async def reset_test_database():
    admin = make_engine(TEST_DATABASE_URL.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": TEST_DATABASE_URL.database},
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{TEST_DATABASE_URL.database}"'))
    await admin.dispose()

    # Rebuild the tables from the models, so they always match the current code.
    engine = make_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


async def empty_tables():
    engine = make_engine()
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE conversations CASCADE"))
    await engine.dispose()


@pytest.fixture(scope="session")
def test_engine():
    """Runs once per test run."""
    asyncio.run(reset_test_database())
    return make_engine()


@pytest.fixture(autouse=True)
def store(test_engine):
    """Runs for every test (autouse): a fresh, empty database behind the app's store."""
    asyncio.run(empty_tables())
    app.dependency_overrides[get_store] = lambda: PostgresConversationStore(
        async_sessionmaker(test_engine, expire_on_commit=False)
    )
    yield
    app.dependency_overrides.pop(get_store)
