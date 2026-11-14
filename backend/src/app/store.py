import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app import models
from app.db import Sessions
from app.llm import Message


class PostgresConversationStore:
    """Saves and loads conversations.

    Each method opens its own short session, because a websocket can stay open for hours and
    shouldn't hold a database connection the whole time.
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession]):
        self._sessions = sessions

    async def create(self) -> uuid.UUID:
        async with self._sessions() as session:
            conversation = models.Conversation()
            session.add(conversation)
            await session.commit()
            return conversation.id

    async def load(self, conversation_id: uuid.UUID) -> list[Message] | None:
        """The conversation's messages, oldest first, or None if it doesn't exist."""
        async with self._sessions() as session:
            # Load the messages in the same go: async SQLAlchemy can't lazy-load them later.
            conversation = await session.get(
                models.Conversation,
                conversation_id,
                options=[selectinload(models.Conversation.messages)],
            )
            if conversation is None:
                return None
            return [
                Message.model_validate(
                    {"role": m.role, "parts": m.parts, "provider": m.provider, "model": m.model}
                )
                for m in conversation.messages
            ]

    async def append(self, conversation_id: uuid.UUID, *messages: Message) -> None:
        # In one transaction, so a turn's messages are saved all together or not at all.
        async with self._sessions() as session:
            session.add_all(
                models.Message(
                    conversation_id=conversation_id,
                    role=message.role,
                    parts=[part.model_dump(mode="json") for part in message.parts],
                    provider=message.provider,
                    model=message.model,
                    raw=message.raw,
                )
                for message in messages
            )
            await session.commit()


def get_store(sessions: Sessions) -> PostgresConversationStore:
    return PostgresConversationStore(sessions)
