import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db import Session
from app.llm import ChatMessage
from app.models import Conversation, Message


class PostgresConversationStore:
    """Saves and loads conversations.

    Each method opens its own short session, because a websocket can stay open for hours and
    shouldn't hold a database connection the whole time.
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession]):
        self._sessions = sessions

    async def create(self) -> uuid.UUID:
        async with self._sessions() as session:
            conversation = Conversation()
            session.add(conversation)
            await session.commit()
            return conversation.id

    async def load(self, conversation_id: uuid.UUID) -> list[ChatMessage] | None:
        """The conversation's messages, oldest first, or None if it doesn't exist."""
        async with self._sessions() as session:
            # Load the messages in the same go: async SQLAlchemy can't lazy-load them later.
            conversation = await session.get(
                Conversation, conversation_id, options=[selectinload(Conversation.messages)]
            )
            if conversation is None:
                return None
            return [{"role": m.role, "content": m.content} for m in conversation.messages]

    async def append(self, conversation_id: uuid.UUID, *messages: ChatMessage) -> None:
        # In one transaction, so a turn's messages are saved all together or not at all.
        async with self._sessions() as session:
            session.add_all(
                Message(
                    conversation_id=conversation_id,
                    role=message["role"],
                    content=message["content"],
                )
                for message in messages
            )
            await session.commit()


def get_store() -> PostgresConversationStore:
    return PostgresConversationStore(Session)
