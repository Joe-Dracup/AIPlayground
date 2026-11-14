from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest
from anthropic.types.beta import BetaMessage
from pydantic import SecretStr

from app.config import settings
from app.llm import (
    FakeLLM,
    Finished,
    LLMError,
    Message,
    ProviderPart,
    ReasoningPart,
    TextDelta,
    TextPart,
    ToolCallPart,
    ToolResultPart,
    ToolSpec,
    get_llm,
)
from app.llm.anthropic_llm import AnthropicLLM, from_anthropic, to_anthropic, to_anthropic_tool

THINKING = {"type": "thinking", "thinking": "The user wants the time.", "signature": "sig123"}


def assistant(*parts) -> Message:
    return Message(role="assistant", parts=list(parts))


def test_messages_load_from_stored_json_by_part_type():
    message = Message.model_validate(
        {
            "role": "assistant",
            "parts": [
                {"type": "text", "text": "Let me check."},
                {"type": "tool_call", "id": "call_1", "name": "get_time", "arguments": {}},
            ],
        }
    )
    assert message.parts == [
        TextPart(text="Let me check."),
        ToolCallPart(id="call_1", name="get_time", arguments={}),
    ]


def test_raw_is_not_part_of_a_messages_json():
    message = Message(role="assistant", parts=[TextPart(text="Hi")], raw={"id": "msg_1"})
    assert "raw" not in message.model_dump()


def test_reads_every_kind_of_block():
    fallback = {"type": "fallback", "from": {"model": "a"}, "to": {"model": "b"}}
    tool_use = {"type": "tool_use", "id": "toolu_1", "name": "get_time", "input": {"x": 1}}
    assert from_anthropic([THINKING, {"type": "text", "text": "Hi"}, tool_use, fallback]) == [
        ReasoningPart(provider="anthropic", text="The user wants the time.", opaque=THINKING),
        TextPart(text="Hi"),
        ToolCallPart(id="toolu_1", name="get_time", arguments={"x": 1}),
        ProviderPart(provider="anthropic", data=fallback),
    ]


def test_anthropic_blocks_survive_a_round_trip_unchanged():
    blocks = [
        THINKING,
        {"type": "fallback", "from": {"model": "a"}, "to": {"model": "b"}},
        {"type": "text", "text": "Checking."},
        {"type": "tool_use", "id": "toolu_1", "name": "get_time", "input": {}},
    ]
    [request] = to_anthropic([assistant(*from_anthropic(blocks))])
    assert request == {"role": "assistant", "content": blocks}


def test_tool_results_are_sent_in_a_user_message():
    result = ToolResultPart(call_id="toolu_1", content="Error!", is_error=True)
    assert to_anthropic([Message(role="tool", parts=[result])]) == [
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": "Error!",
                    "is_error": True,
                }
            ],
        }
    ]


def test_consecutive_messages_with_the_same_role_are_merged():
    results = Message(role="tool", parts=[ToolResultPart(call_id="toolu_1", content="12:00")])
    request = to_anthropic([Message.user("hi"), Message.user("anyone there?"), results])
    assert len(request) == 1
    assert [block["type"] for block in request[0]["content"]] == ["text", "text", "tool_result"]


def test_other_providers_reasoning_and_empty_text_are_left_out():
    other = ReasoningPart(provider="openai", text="...", opaque={"encrypted_content": "x"})
    request = to_anthropic(
        [
            Message.user("hi"),
            assistant(other, TextPart(text="")),
            assistant(TextPart(text="Hello")),
        ]
    )
    assert request == [
        {"role": "user", "content": [{"type": "text", "text": "hi"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "Hello"}]},
    ]


def test_tool_specs_become_anthropic_tools():
    spec = ToolSpec("get_time", "Get the time.", {"type": "object", "properties": {}})
    assert to_anthropic_tool(spec) == {
        "name": "get_time",
        "description": "Get the time.",
        "input_schema": {"type": "object", "properties": {}},
    }


class StubStream:
    """Stands in for the SDK's message stream: some text, then the final message."""

    def __init__(self, texts: list[str], final: BetaMessage, error: Exception | None):
        self._texts = texts
        self._final = final
        self._error = error

    async def __aenter__(self):
        if self._error is not None:
            raise self._error
        return self

    async def __aexit__(self, *exc_info):
        return False

    @property
    async def text_stream(self):
        for text in self._texts:
            yield text

    async def get_final_message(self) -> BetaMessage:
        return self._final


class StubAnthropic:
    """Stands in for AsyncAnthropic, recording each request instead of calling the API."""

    def __init__(self, content=(), stop_reason="end_turn", texts=(), error=None):
        self.requests: list[dict[str, Any]] = []
        final = BetaMessage.model_validate(
            {
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-test",
                "content": list(content),
                "stop_reason": stop_reason,
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        )

        def stream(**request):
            self.requests.append(request)
            return StubStream(list(texts), final, error)

        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=stream))


async def reply_events(client: StubAnthropic, messages=None, tools=(), system="Be nice.") -> list:
    llm = AnthropicLLM(client, model="claude-test")
    return [
        event
        async for event in llm.stream_reply(system, messages or [Message.user("hi")], list(tools))
    ]


@pytest.mark.anyio
async def test_streams_text_then_finishes_with_the_reply():
    client = StubAnthropic(
        content=[THINKING, {"type": "text", "text": "Hi there"}], texts=["Hi", " there"]
    )
    *deltas, finished = await reply_events(client)

    assert deltas == [TextDelta("Hi"), TextDelta(" there")]
    assert isinstance(finished, Finished)
    assert finished.stop_reason == "end"
    expected = Message(
        role="assistant",
        parts=[
            ReasoningPart(provider="anthropic", text=THINKING["thinking"], opaque=THINKING),
            TextPart(text="Hi there"),
        ],
        provider="anthropic",
        model="claude-test",
    )
    assert finished.message.model_dump() == expected.model_dump()
    assert finished.message.raw["id"] == "msg_1"


@pytest.mark.anyio
async def test_sends_the_system_prompt_conversation_and_tools_in_anthropics_format():
    client = StubAnthropic(content=[{"type": "text", "text": "Hi"}])
    spec = ToolSpec("get_time", "Get the time.", {"type": "object", "properties": {}})
    messages = [Message.user("what time is it")]
    await reply_events(client, messages, [spec])

    [request] = client.requests
    assert request["model"] == "claude-test"
    assert request["system"] == "Be nice."
    assert request["messages"] == to_anthropic(messages)
    assert request["tools"] == [to_anthropic_tool(spec)]
    assert request["max_tokens"] == AnthropicLLM.MAX_TOKENS
    assert request["fallbacks"] == "default"


@pytest.mark.anyio
async def test_a_tool_call_finishes_waiting_for_tool_results():
    tool_use = {"type": "tool_use", "id": "toolu_1", "name": "get_time", "input": {}}
    *_, finished = await reply_events(StubAnthropic(content=[tool_use], stop_reason="tool_use"))
    assert finished.stop_reason == "tool_calls"
    assert finished.message.tool_calls == [
        ToolCallPart(id="toolu_1", name="get_time", arguments={})
    ]


@pytest.mark.anyio
async def test_a_reply_cut_off_at_the_length_limit_finishes_with_length():
    client = StubAnthropic(
        content=[{"type": "text", "text": "Once upon"}], stop_reason="max_tokens"
    )
    *_, finished = await reply_events(client)
    assert finished.stop_reason == "length"


@pytest.mark.anyio
async def test_a_tool_call_cut_off_at_the_length_limit_is_an_error():
    tool_use = {"type": "tool_use", "id": "toolu_1", "name": "get_time", "input": {}}
    with pytest.raises(LLMError, match="too long"):
        await reply_events(StubAnthropic(content=[tool_use], stop_reason="max_tokens"))


@pytest.mark.anyio
async def test_a_refusal_is_an_error():
    with pytest.raises(LLMError, match="declined"):
        await reply_events(StubAnthropic(stop_reason="refusal"))


@pytest.mark.anyio
async def test_api_errors_become_a_safe_llm_error():
    error = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.test"))
    with pytest.raises(LLMError) as raised:
        await reply_events(StubAnthropic(error=error))
    assert str(raised.value) == "The AI service returned an error. Try again in a moment."
    assert raised.value.__cause__ is error


def test_uses_anthropic_when_an_api_key_is_set(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", SecretStr("test-key"))
    assert isinstance(get_llm(), AnthropicLLM)


def test_uses_the_fake_llm_without_an_api_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    assert isinstance(get_llm(), FakeLLM)
