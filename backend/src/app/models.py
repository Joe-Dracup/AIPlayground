import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
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
