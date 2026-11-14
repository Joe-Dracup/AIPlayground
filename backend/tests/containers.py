"""A throwaway Postgres for tests, shared by pytest and the application tests' API server."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from testcontainers.community.postgres import PostgresContainer
from testcontainers.core.image import DockerImage

BACKEND_DIR = Path(__file__).parent.parent


def run_migrations(url: str) -> None:
    config = Config(toml_file=BACKEND_DIR / "pyproject.toml")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


@contextmanager
def test_database() -> Generator[str]:
    """Starts Postgres from db/Dockerfile, runs the migrations, and yields its URL. Needs Docker.

    The container is deleted on exit. The image is kept, so later runs don't rebuild it.
    """
    with (
        DockerImage(path=BACKEND_DIR / "db", tag="aiplayground-test-db", clean_up=False) as image,
        PostgresContainer(str(image), driver="asyncpg") as postgres,
    ):
        url = postgres.get_connection_url()
        run_migrations(url)
        yield url
