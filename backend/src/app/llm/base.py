from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.llm.messages import Message


class LLMError(Exception):
    """A reply couldn't be produced. The message is safe to show to the user."""


# Why a reply ended: finished, waiting for tool results, or cut off at the length limit.
StopReason = Literal["end", "tool_calls", "length"]


@dataclass(frozen=True)
class TextDelta:
    """A piece of the reply's text, to show while the rest streams in."""

    text: str


@dataclass(frozen=True)
class Finished:
    """The complete reply. Always the last event."""

    message: Message
    stop_reason: StopReason


type LLMEvent = TextDelta | Finished


@dataclass(frozen=True)
class ToolSpec:
    """A tool as offered to an LLM. `parameters` is the JSON Schema for its input."""

    name: str
    description: str
    parameters: dict[str, Any]


class LLMClient(Protocol):
    """Anything that can stream one reply to a conversation, given the tools it may call.

    Yields TextDelta events as the text arrives, then one Finished event. Raises LLMError if the
    reply fails, possibly after some text has already been sent.
    """

    def stream_reply(
        self, messages: list[Message], tools: list[ToolSpec]
    ) -> AsyncIterator[LLMEvent]: ...
