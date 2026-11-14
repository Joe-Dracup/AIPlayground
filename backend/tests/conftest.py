import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.image import DockerImage

from app.db import Base, get_sessions
from app.main import app
from app.seed import seed

BACKEND_DIR = Path(__file__).parent.parent


def run_migrations(url: str) -> None:
    """Build the schema the same way dev and production do, PostGIS and all."""
    config = Config(toml_file=BACKEND_DIR / "pyproject.toml")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def database_url():
    """A throwaway Postgres for the whole test run, deleted afterwards. Needs Docker running.

    Built from the same db/Dockerfile as the dev database, so it has the same extensions.
    """
    # clean_up=False keeps the image after the run, so later runs reuse it instead of rebuilding.
    with DockerImage(path=BACKEND_DIR / "db", tag="aiplayground-test-db", clean_up=False) as image:
        with PostgresContainer(str(image), driver="asyncpg") as postgres:
            url = postgres.get_connection_url()
            run_migrations(url)
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
