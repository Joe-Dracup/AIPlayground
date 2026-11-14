import asyncio

import pytest
from containers import test_database
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.db import Base, get_sessions
from app.main import app
from app.seed import seed


@pytest.fixture(scope="session")
def database_url():
    with test_database() as url:
        yield url


@pytest.fixture(scope="session")
def test_engine(database_url):
    # NullPool: no connections kept between uses. The tests and the app under test run on
    # different event loops, and an asyncpg connection only works on the loop that opened it.
    return create_async_engine(database_url, poolclass=NullPool)


async def empty_tables(engine: AsyncEngine):
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))


@pytest.fixture(autouse=True)
def sessions(test_engine):
    """Runs for every test (autouse): a fresh, empty database behind everything in the app."""
    asyncio.run(empty_tables(test_engine))
    sessions = async_sessionmaker(test_engine, expire_on_commit=False)
    app.dependency_overrides[get_sessions] = lambda: sessions
    yield sessions
    app.dependency_overrides.pop(get_sessions)


@pytest.fixture
def seeded(sessions):
    """Loads the sample places from app.seed into the test database."""

    async def load():
        async with sessions() as session, session.begin():
            await seed(session)

    asyncio.run(load())
