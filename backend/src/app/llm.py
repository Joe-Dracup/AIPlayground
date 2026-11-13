import asyncio
import re
from collections.abc import AsyncIterator
from typing import Protocol

ChatMessage = dict[str, str]


class LLMClient(Protocol):
    """Anything that can stream a reply to a conversation, one text chunk at a time."""

    def stream_reply(self, messages: list[ChatMessage]) -> AsyncIterator[str]: ...


class FakeLLM:
    """Replies without calling a real API. Used in tests, and until a real client is wired in.

    `replies` maps the user's latest message to the reply for it. Anything else is echoed back.
    `delay` is the pause in seconds between chunks, to make streaming visible in the UI.
    """

    def __init__(self, replies: dict[str, str] | None = None, delay: float = 0):
        self.replies = replies or {}
        self.delay = delay
        # Every conversation this was asked to reply to, so tests can check what it was sent.
        self.calls: list[list[ChatMessage]] = []

    async def stream_reply(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        # Copy, because the caller keeps appending to the same list after this call.
        self.calls.append(list(messages))
        last = messages[-1]["content"]
        reply = self.replies.get(last, f"You said: {last}")
        # Stream word by word, keeping the spaces, like a real LLM sends small pieces.
        for chunk in re.findall(r"\s*\S+", reply):
            await asyncio.sleep(self.delay)
            yield chunk


def get_llm() -> LLMClient:
    return FakeLLM(
        replies={
            "hi": "Hi, how are you?",
            "doing well thanks": "Good, hope your day keeps going well",
        },
        delay=0.08,
    )
