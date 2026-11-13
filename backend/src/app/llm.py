import asyncio
import logging
import re
from collections.abc import AsyncIterator
from functools import cache
from typing import Protocol

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

ChatMessage = dict[str, str]


class LLMError(Exception):
    """A reply couldn't be produced. The message is safe to show to the user."""


class LLMClient(Protocol):
    """Anything that can stream a reply to a conversation, one text chunk at a time.

    Raises LLMError if the reply fails, possibly after some chunks have already been sent.
    """

    def stream_reply(self, messages: list[ChatMessage]) -> AsyncIterator[str]: ...


class AnthropicLLM:
    """Streams replies from Claude through the Anthropic API."""

    # Caps each reply's length, and so its cost. Thinking counts towards it too.
    MAX_TOKENS = 16000

    def __init__(self, client: anthropic.AsyncAnthropic, model: str):
        self._client = client
        self._model = model

    async def stream_reply(self, messages: list[ChatMessage]) -> AsyncIterator[str]:
        try:
            async with self._client.beta.messages.stream(
                model=self._model,
                max_tokens=self.MAX_TOKENS,
                messages=messages,
                # If Claude's safety checks decline a request, retry it on Anthropic's
                # recommended fallback model instead of failing.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                final = await stream.get_final_message()
        except anthropic.APIError as e:
            # Full details in the server log; the user gets a short, safe message.
            logger.exception("Anthropic API request failed")
            raise LLMError("The AI service returned an error. Try again in a moment.") from e

        if final.stop_reason == "refusal":
            raise LLMError("Claude declined to answer that.")


class FakeLLM:
    """Replies without calling a real API. Used in tests, and when no API key is set.

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


# Cached so every chat shares one client (and its connection pool): a singleton.
@cache
def _anthropic_client(api_key: str) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=api_key)


def get_llm() -> LLMClient:
    if settings.anthropic_api_key is not None:
        client = _anthropic_client(settings.anthropic_api_key.get_secret_value())
        return AnthropicLLM(client, model=settings.anthropic_model)

    return FakeLLM(
        replies={
            "hi": "Hi, how are you?",
            "doing well thanks": "Good, hope your day keeps going well",
        },
        delay=0.08,
    )
