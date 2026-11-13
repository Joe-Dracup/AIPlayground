from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Parent class for every table model. Its metadata is what Alembic compares against the database."""

    # Give constraints and indexes predictable names, so later migrations can find them to change or drop.
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


# Doesn't connect yet: connections are opened on first use and pooled.
engine = create_async_engine(settings.database_url)
Session = async_sessionmaker(engine, expire_on_commit=False)
