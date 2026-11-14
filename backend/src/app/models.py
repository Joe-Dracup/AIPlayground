import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography, WKBElement
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Conversation(Base):
    __tablename__ = "conversations"

    # A UUID rather than 1, 2, 3... because it goes in the URL and shouldn't be guessable.
    # default= fills it in Python; server_default= covers inserts made outside the app.
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=func.gen_random_uuid()
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.id", passive_deletes=True
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (CheckConstraint("role IN ('user', 'assistant')", name="role"),)

    # Auto-incrementing, so it also gives the order messages were added in.
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str]
    # JSONB so it can hold either plain text or the list of content blocks the Claude API returns.
    content: Mapped[str | list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Place(Base):
    """A point of interest that can be searched for, brought in by an import job."""

    __tablename__ = "places"
    __table_args__ = (
        # Re-running an import updates each place instead of adding it again.
        UniqueConstraint("source", "source_id"),
        # GIN indexes the array's individual values, so "has these tags" queries are fast.
        Index("ix_places_tags", "tags", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Where it came from, and its id there, e.g. "osm" and "node/12345".
    source: Mapped[str]
    source_id: Mapped[str]
    name: Mapped[str]
    # One of our own categories ("cafe", "pub", "park"...), mapped from the source's vocabulary.
    category: Mapped[str] = mapped_column(index=True)
    # Longitude/latitude on a round Earth (4326 is the GPS coordinate system), so distances come
    # out in metres. GeoAlchemy2 adds a spatial (GiST) index for it automatically.
    location: Mapped[WKBElement] = mapped_column(Geography("POINT", srid=4326))
    # Our own characteristics ("wifi", "dog_friendly"...), mapped from the source data.
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    # The source's record as it was imported, so places can be re-tagged without fetching again.
    source_data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
