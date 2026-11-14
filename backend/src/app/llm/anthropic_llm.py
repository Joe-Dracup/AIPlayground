import logging
from collections.abc import AsyncIterator
from typing import Any

import anthropic

from app.llm.base import Finished, LLMError, LLMEvent, StopReason, TextDelta, ToolSpec
from app.llm.messages import (
    Message,
    Part,
    ProviderPart,
    ReasoningPart,
    TextPart,
    ToolCallPart,
    ToolResultPart,
)

logger = logging.getLogger(__name__)

PROVIDER = "anthropic"

_STOP_REASONS: dict[str, StopReason] = {"tool_use": "tool_calls", "max_tokens": "length"}


class AnthropicLLM:
    """Streams replies from Claude through the Anthropic API."""

    # Caps each reply's length, and so its cost. Thinking counts towards it too.
    MAX_TOKENS = 16000

    def __init__(self, client: anthropic.AsyncAnthropic, model: str):
        self._client = client
        self._model = model

    async def stream_reply(
        self, system: str, messages: list[Message], tools: list[ToolSpec]
    ) -> AsyncIterator[LLMEvent]:
        try:
            async with self._client.beta.messages.stream(
                model=self._model,
                max_tokens=self.MAX_TOKENS,
                system=system,
                messages=to_anthropic(messages),
                tools=[to_anthropic_tool(tool) for tool in tools],
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

        raw = final.model_dump(mode="json", by_alias=True, exclude_none=True)
        yield Finished(
            Message(
                role="assistant",
                parts=from_anthropic(raw["content"]),
                provider=PROVIDER,
                model=final.model,
                raw=raw,
            ),
            _STOP_REASONS.get(final.stop_reason or "", "end"),
        )


def to_anthropic_tool(tool: ToolSpec) -> dict[str, Any]:
    return {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}


def to_anthropic(messages: list[Message]) -> list[dict[str, Any]]:
    """Our messages as the Anthropic API's: tool results go in user messages, and consecutive
    messages with the same role are merged."""
    result: list[dict[str, Any]] = []
    for message in messages:
        blocks = [block for part in message.parts if (block := _to_anthropic_block(part))]
        if not blocks:
            continue
        role = "assistant" if message.role == "assistant" else "user"
        if result and result[-1]["role"] == role:
            result[-1]["content"].extend(blocks)
        else:
            result.append({"role": role, "content": blocks})
    return result


def _to_anthropic_block(part: Part) -> dict[str, Any] | None:
    match part:
        case TextPart(text=text):
            # The API rejects empty text blocks.
            return {"type": "text", "text": text} if text else None
        case ToolCallPart(id=id, name=name, arguments=arguments):
            return {"type": "tool_use", "id": id, "name": name, "input": arguments}
        case ToolResultPart(call_id=call_id, content=content, is_error=is_error):
            return {
                "type": "tool_result",
                "tool_use_id": call_id,
                "content": content,
                "is_error": is_error,
            }
        # Thinking and other Anthropic-only blocks are sent back exactly as they arrived.
        case ReasoningPart(provider="anthropic", opaque=block):
            return block
        case ProviderPart(provider="anthropic", data=block):
            return block
        case _:
            # Another provider's reasoning or content, which Anthropic can't use.
            return None


def from_anthropic(content: list[dict[str, Any]]) -> list[Part]:
    parts: list[Part] = []
    for block in content:
        match block["type"]:
            case "text":
                parts.append(TextPart(text=block["text"]))
            case "tool_use":
                parts.append(
                    ToolCallPart(id=block["id"], name=block["name"], arguments=block["input"])
                )
            case "thinking" | "redacted_thinking":
                parts.append(
                    ReasoningPart(provider=PROVIDER, text=block.get("thinking"), opaque=block)
                )
            case _:
                parts.append(ProviderPart(provider=PROVIDER, data=block))
    return parts
