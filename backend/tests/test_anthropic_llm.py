from app.llm import (
    Message,
    ProviderPart,
    ReasoningPart,
    TextPart,
    ToolCallPart,
    ToolResultPart,
    ToolSpec,
)
from app.llm.anthropic_llm import from_anthropic, to_anthropic, to_anthropic_tool

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
