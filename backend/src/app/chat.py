import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.llm import Finished, LLMClient, LLMError, Message, TextDelta
from app.tools.base import ToolRegistry

# The most replies the LLM gets in one turn. Each one can call tools, so this stops a confused
# model calling tools forever (and running up the bill).
MAX_STEPS = 10


@dataclass(frozen=True)
class TurnComplete:
    """The last event of a turn: every message the turn added, in order, ready to save."""

    messages: list[Message]


type TurnEvent = TextDelta | TurnComplete


async def run_turn(
    llm: LLMClient, tools: ToolRegistry, messages: list[Message]
) -> AsyncIterator[TurnEvent]:
    """Get the LLM's reply to `messages`, running any tools it asks for along the way.

    The LLM replies, we run the tools it asked for and send back the results, and it replies
    again, until it answers without calling a tool. The new messages are only handed over at the
    end, so a turn that fails part way leaves nothing half-saved. Raises LLMError if it fails.
    """
    new_messages: list[Message] = []
    wrote_text = False

    for _ in range(MAX_STEPS):
        reply: Finished | None = None
        new_step = True
        async for event in llm.stream_reply(messages + new_messages, tools.specs()):
            match event:
                case TextDelta():
                    if new_step and wrote_text:
                        # Keep text from either side of a tool call apart, as the history does.
                        yield TextDelta("\n\n")
                    new_step = False
                    wrote_text = True
                    yield event
                case Finished():
                    reply = event
        assert reply is not None, "stream_reply must end with a Finished event"

        new_messages.append(reply.message)
        if reply.stop_reason != "tool_calls":
            yield TurnComplete(new_messages)
            return

        # The LLM can ask for several tools at once, so run them at the same time.
        results = await asyncio.gather(*(tools.run(call) for call in reply.message.tool_calls))
        new_messages.append(Message(role="tool", parts=list(results)))

    raise LLMError(f"Gave up after {MAX_STEPS} rounds of tool calls.")


def display_history(messages: list[Message]) -> list[dict[str, str]]:
    """The conversation as the chat UI shows it: plain text, one bubble per message.

    Tool calls and their results are left out, and a reply split up by tool calls becomes one
    bubble again.
    """
    shown: list[dict[str, str]] = []
    for message in messages:
        match message.role:
            case "user":
                shown.append({"role": "user", "content": message.text})
            case "assistant" if shown and shown[-1]["role"] == "assistant":
                previous = shown[-1]["content"]
                shown[-1]["content"] = "\n\n".join(p for p in (previous, message.text) if p)
            case "assistant":
                shown.append({"role": "assistant", "content": message.text})
    return shown
