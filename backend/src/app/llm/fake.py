import asyncio
import json
import re
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any

from app.llm.base import Finished, LLMEvent, TextDelta, ToolSpec
from app.llm.messages import Message, TextPart, ToolCallPart

PROVIDER = "fake"


@dataclass(frozen=True)
class FakeToolCall:
    """A FakeLLM step that calls a tool.

    `input` is either the tool input, or a function that builds it from the previous tool's result.
    """

    name: str
    input: dict[str, Any] | Callable[[str], dict[str, Any]]


@dataclass(frozen=True)
class FakeRaise:
    """A FakeLLM step that fails with `error`, like a bug or an unexpected response."""

    error: Exception


type FakeStep = str | FakeToolCall | FakeRaise


class FakeLLM:
    """Replies without calling a real API. Used in tests, and when no API key is set.

    `replies` maps a user message to the reply for it: text, a FakeToolCall, or a list of steps
    played in order, one per reply. Anything else is echoed back, and tool results left over
    after the steps run out come back as "Tool said: ...".
    `delay` is the pause in seconds between chunks, to make streaming visible in the UI.
    """

    def __init__(
        self, replies: dict[str, FakeStep | list[FakeStep]] | None = None, delay: float = 0
    ):
        self.replies = dict(replies or {})
        self.delay = delay
        # Every conversation this was asked to reply to, so tests can check what it was sent.
        self.calls: list[list[Message]] = []
        self._tool_calls_made = 0

    async def stream_reply(
        self, messages: list[Message], tools: list[ToolSpec]
    ) -> AsyncIterator[LLMEvent]:
        # Copy, because the caller keeps appending to the same list after this call.
        self.calls.append(list(messages))
        reply = self._next_step(messages)

        if isinstance(reply, FakeRaise):
            raise reply.error

        if isinstance(reply, FakeToolCall):
            self._tool_calls_made += 1
            arguments = reply.input
            if callable(arguments):
                arguments = arguments(messages[-1].tool_results[0].content)
            call = ToolCallPart(
                id=f"call_fake_{self._tool_calls_made}", name=reply.name, arguments=arguments
            )
            yield Finished(_assistant([call]), "tool_calls")
            return

        # Stream word by word, keeping the spaces, like a real LLM sends small pieces.
        for chunk in re.findall(r"\s*\S+", reply):
            await asyncio.sleep(self.delay)
            yield TextDelta(chunk)
        yield Finished(_assistant([TextPart(text=reply)]), "end")

    def _next_step(self, messages: list[Message]) -> FakeStep:
        prompt_index = max(i for i, message in enumerate(messages) if message.role == "user")
        prompt = messages[prompt_index].text
        steps = self.replies.get(prompt, f"You said: {prompt}")
        if not isinstance(steps, list):
            steps = [steps]

        step = sum(1 for message in messages[prompt_index:] if message.role == "assistant")
        if step < len(steps):
            return steps[step]
        return " ".join(f"Tool said: {result.content}" for result in messages[-1].tool_results)


def _assistant(parts: list[TextPart | ToolCallPart]) -> Message:
    return Message(role="assistant", parts=list(parts), provider=PROVIDER)


# The replies FakeLLM gives when it stands in for a real LLM: in dev without an API key, and in the
# application tests.
FAKE_REPLIES: dict[str, FakeStep | list[FakeStep]] = {
    "hi": "Hi, how are you?",
    "doing well thanks": "Good, hope your day keeps going well",
    "what time is it": FakeToolCall("get_time", {"timezone": "Europe/London"}),
    "find piccadilly": FakeToolCall("find_place", {"query": "Piccadilly"}),
    "pubs near piccadilly": [
        FakeToolCall("find_place", {"query": "Manchester Piccadilly"}),
        FakeToolCall(
            "search_places",
            lambda found: {"near_place_id": json.loads(found)[0]["id"], "category": "pub"},
        ),
    ],
    "break": FakeRaise(RuntimeError("FakeLLM was asked to break")),
}
