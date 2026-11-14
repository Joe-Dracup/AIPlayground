import asyncio
import logging
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import cache
from typing import Any, Protocol

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)

# A message in the Claude API's format: a role, and content that's either plain text or a list of
# content blocks (text, thinking, tool_use, tool_result, ...).
ChatMessage = dict[str, Any]


class LLMError(Exception):
    """A reply couldn't be produced. The message is safe to show to the user."""


@dataclass(frozen=True)
class TextDelta:
    """A piece of the reply's text, to show while the rest streams in."""

    text: str


@dataclass(frozen=True)
class Finished:
    """The complete reply. Always the last event.

    `content` is the assistant message's content blocks, ready to save and send back to the API.
    `stop_reason` is "tool_use" when Claude is waiting for tool results, "end_turn" when it's done.
    """

    content: list[dict[str, Any]]
    stop_reason: str | None


type LLMEvent = TextDelta | Finished


class LLMClient(Protocol):
    """Anything that can stream one reply to a conversation, given the tools it may call.

    Yields TextDelta events as the text arrives, then one Finished event. Raises LLMError if the
    reply fails, possibly after some text has already been sent.
    """

    def stream_reply(
        self, messages: list[ChatMessage], tools: list[dict[str, Any]]
    ) -> AsyncIterator[LLMEvent]: ...


class AnthropicLLM:
    """Streams replies from Claude through the Anthropic API."""

    # Caps each reply's length, and so its cost. Thinking counts towards it too.
    MAX_TOKENS = 16000

    def __init__(self, client: anthropic.AsyncAnthropic, model: str):
        self._client = client
        self._model = model

    async def stream_reply(
        self, messages: list[ChatMessage], tools: list[dict[str, Any]]
    ) -> AsyncIterator[LLMEvent]:
        try:
            async with self._client.beta.messages.stream(
                model=self._model,
                max_tokens=self.MAX_TOKENS,
                messages=messages,
                tools=tools,
                # If Claude's safety checks decline a request, retry it on Anthropic's
                # recommended fallback model instead of failing.
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            ) as stream:
                async for text in stream.text_stream:
                    yield TextDelta(text)
                final = await stream.get_final_message()
        except anthropic.APIError as e:
            # Full details in the server log; the user gets a short, safe message.
            logger.exception("Anthropic API request failed")
            raise LLMError("The AI service returned an error. Try again in a moment.") from e

        if final.stop_reason == "refusal":
            raise LLMError("Claude declined to answer that.")
        if final.stop_reason == "max_tokens" and any(b.type == "tool_use" for b in final.content):
            # A tool call was cut off part way through, so its input can't be trusted.
            raise LLMError("The reply was too long. Try asking for something smaller.")

        # Every block is kept exactly as it came, because it's sent back on later requests, and
        # the API rejects thinking blocks that have been changed.
        content = [
            block.model_dump(mode="json", by_alias=True, exclude_none=True)
            for block in final.content
        ]
        yield Finished(content, final.stop_reason)


@dataclass(frozen=True)
class FakeToolCall:
    """A FakeLLM reply that asks for a tool to be run, instead of answering with text."""

    name: str
    input: dict[str, Any]


class FakeLLM:
    """Replies without calling a real API. Used in tests, and when no API key is set.

    `replies` maps the user's latest message to the reply for it: text, or a FakeToolCall.
    Anything else is echoed back, and tool results come back as "Tool said: ...".
    `delay` is the pause in seconds between chunks, to make streaming visible in the UI.
    """

    def __init__(self, replies: dict[str, str | FakeToolCall] | None = None, delay: float = 0):
        self.replies = replies or {}
        self.delay = delay
        # Every conversation this was asked to reply to, so tests can check what it was sent.
        self.calls: list[list[ChatMessage]] = []
        self._tool_calls_made = 0

    async def stream_reply(
        self, messages: list[ChatMessage], tools: list[dict[str, Any]]
    ) -> AsyncIterator[LLMEvent]:
        # Copy, because the caller keeps appending to the same list after this call.
        self.calls.append(list(messages))
        reply = self._reply_to(messages[-1]["content"])

        if isinstance(reply, FakeToolCall):
            self._tool_calls_made += 1
            tool_use = {
                "type": "tool_use",
                "id": f"toolu_fake_{self._tool_calls_made}",
                "name": reply.name,
                "input": reply.input,
            }
            yield Finished([tool_use], "tool_use")
            return

        # Stream word by word, keeping the spaces, like a real LLM sends small pieces.
        for chunk in re.findall(r"\s*\S+", reply):
            await asyncio.sleep(self.delay)
            yield TextDelta(chunk)
        yield Finished([{"type": "text", "text": reply}], "end_turn")

    def _reply_to(self, content: str | list[dict[str, Any]]) -> str | FakeToolCall:
        if isinstance(content, str):
            return self.replies.get(content, f"You said: {content}")
        # Otherwise it's the tool_result blocks for the tool calls in the previous reply.
        return " ".join(f"Tool said: {block['content']}" for block in content)


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
            "what time is it": FakeToolCall("get_time", {"timezone": "Europe/London"}),
        },
        delay=0.08,
    )
