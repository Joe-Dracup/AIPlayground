import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

from app.llm import (
    FakeLLM,
    FakeRaise,
    FakeToolCall,
    Finished,
    LLMError,
    Message,
    TextDelta,
    TextPart,
    ToolCallPart,
    ToolResultPart,
    get_llm,
)
from app.main import CONVERSATION_NOT_FOUND, app
from app.tools import get_tools
from app.tools.base import Tool, ToolRegistry


class NoInput(BaseModel):
    pass


async def _always_noon(args: NoInput) -> str:
    return "12:00"


# A clock that always gives the same answer, so tests can check exact replies.
fixed_clock = Tool(
    name="get_time", description="Get the time.", input_model=NoInput, run=_always_noon
)


@pytest.fixture
def llm():
    fake = FakeLLM(replies={"hi": "Hello there", "what time is it": FakeToolCall("get_time", {})})
    app.dependency_overrides[get_llm] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_llm)


@pytest.fixture
def tools():
    registry = ToolRegistry([fixed_clock])
    app.dependency_overrides[get_tools] = lambda: registry
    yield registry
    app.dependency_overrides.pop(get_tools)


@pytest.fixture
def client(llm, tools):
    return TestClient(app)


def new_conversation(client) -> str:
    response = client.post("/conversations")
    assert response.status_code == 201
    return response.json()["id"]


def receive_reply(ws) -> list[dict]:
    """Collect every message the server sends for one reply, up to and including "done"."""
    received = []
    while not received or received[-1]["type"] != "done":
        received.append(ws.receive_json())
    return received


def reply_text(ws) -> str:
    return "".join(m["text"] for m in receive_reply(ws) if m["type"] == "delta")


def test_a_new_conversation_starts_with_empty_history(client):
    with client.websocket_connect(f"/ws/{new_conversation(client)}") as ws:
        assert ws.receive_json() == {"type": "history", "messages": []}


def test_streams_the_matching_reply_in_chunks(client):
    with client.websocket_connect(f"/ws/{new_conversation(client)}") as ws:
        ws.receive_json()  # history
        ws.send_text("hi")
        assert receive_reply(ws) == [
            {"type": "delta", "text": "Hello"},
            {"type": "delta", "text": " there"},
            {"type": "done"},
        ]


def test_echoes_messages_without_a_reply(client):
    with client.websocket_connect(f"/ws/{new_conversation(client)}") as ws:
        ws.receive_json()  # history
        ws.send_text("anything else")
        assert reply_text(ws) == "You said: anything else"


def test_sends_the_whole_conversation_to_the_llm(client, llm):
    with client.websocket_connect(f"/ws/{new_conversation(client)}") as ws:
        ws.receive_json()  # history
        ws.send_text("hi")
        receive_reply(ws)
        ws.send_text("again")
        receive_reply(ws)

    assert llm.calls[-1] == [
        Message.user("hi"),
        Message(role="assistant", parts=[TextPart(text="Hello there")], provider="fake"),
        Message.user("again"),
    ]


def test_reconnecting_returns_the_saved_history(client):
    conversation_id = new_conversation(client)
    with client.websocket_connect(f"/ws/{conversation_id}") as ws:
        ws.receive_json()  # history
        ws.send_text("hi")
        receive_reply(ws)

    with client.websocket_connect(f"/ws/{conversation_id}") as ws:
        assert ws.receive_json() == {
            "type": "history",
            "messages": [
                {"role": "user", "content": "hi"},
                {"role": "assistant", "content": "Hello there"},
            ],
        }


class FailingLLM:
    async def stream_reply(self, messages, tools):
        yield TextDelta("Partial")
        raise LLMError("Something broke")


def test_a_failed_reply_is_reported_and_not_saved(client):
    conversation_id = new_conversation(client)
    app.dependency_overrides[get_llm] = lambda: FailingLLM()
    with client.websocket_connect(f"/ws/{conversation_id}") as ws:
        ws.receive_json()  # history
        ws.send_text("hi")
        assert ws.receive_json() == {"type": "delta", "text": "Partial"}
        assert ws.receive_json() == {"type": "error", "message": "Something broke"}

    with client.websocket_connect(f"/ws/{conversation_id}") as ws:
        assert ws.receive_json()["messages"] == [{"role": "user", "content": "hi"}]


def test_an_unknown_conversation_is_closed_as_not_found(client):
    with client.websocket_connect(f"/ws/{uuid.uuid4()}") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == CONVERSATION_NOT_FOUND


def test_runs_a_tool_and_replies_with_the_result(client, llm):
    with client.websocket_connect(f"/ws/{new_conversation(client)}") as ws:
        ws.receive_json()  # history
        ws.send_text("what time is it")
        assert reply_text(ws) == "Tool said: 12:00"

    # The second request carried the LLM's tool call and our result back to it.
    assert llm.calls[-1] == [
        Message.user("what time is it"),
        Message(
            role="assistant",
            parts=[ToolCallPart(id="call_fake_1", name="get_time", arguments={})],
            provider="fake",
        ),
        Message(role="tool", parts=[ToolResultPart(call_id="call_fake_1", content="12:00")]),
    ]


def test_history_shows_a_reply_that_used_tools_as_plain_text(client):
    conversation_id = new_conversation(client)
    with client.websocket_connect(f"/ws/{conversation_id}") as ws:
        ws.receive_json()  # history
        ws.send_text("what time is it")
        receive_reply(ws)

    with client.websocket_connect(f"/ws/{conversation_id}") as ws:
        assert ws.receive_json()["messages"] == [
            {"role": "user", "content": "what time is it"},
            {"role": "assistant", "content": "Tool said: 12:00"},
        ]


class LoopingLLM:
    """Asks for the time every time, and never answers."""

    async def stream_reply(self, messages, tools):
        call = ToolCallPart(id=f"call_{len(messages)}", name="get_time", arguments={})
        yield Finished(Message(role="assistant", parts=[call]), "tool_calls")


def test_gives_up_on_endless_tool_calls(client):
    conversation_id = new_conversation(client)
    app.dependency_overrides[get_llm] = lambda: LoopingLLM()
    with client.websocket_connect(f"/ws/{conversation_id}") as ws:
        ws.receive_json()  # history
        ws.send_text("what time is it")
        assert ws.receive_json() == {
            "type": "error",
            "message": "Gave up after 10 rounds of tool calls.",
        }

    with client.websocket_connect(f"/ws/{conversation_id}") as ws:
        assert ws.receive_json()["messages"] == [{"role": "user", "content": "what time is it"}]


def test_plays_a_list_of_steps_using_earlier_tool_results(client, llm):
    seen = []
    llm.replies["twice"] = [
        FakeToolCall("get_time", {}),
        FakeToolCall("get_time", lambda previous: seen.append(previous) or {}),
    ]
    with client.websocket_connect(f"/ws/{new_conversation(client)}") as ws:
        ws.receive_json()  # history
        ws.send_text("twice")
        assert reply_text(ws) == "Tool said: 12:00"

    assert seen == ["12:00"]
    assert len(llm.calls) == 3


async def _crash(args: NoInput) -> str:
    raise RuntimeError("database is down")


def test_a_failing_tool_is_reported_to_the_llm_and_the_reply_carries_on(client, llm):
    broken = Tool(name="get_time", description="Get the time.", input_model=NoInput, run=_crash)
    app.dependency_overrides[get_tools] = lambda: ToolRegistry([broken])
    with client.websocket_connect(f"/ws/{new_conversation(client)}") as ws:
        ws.receive_json()  # history
        ws.send_text("what time is it")
        assert reply_text(ws) == "Tool said: The tool failed unexpectedly."


def test_an_unexpected_error_is_reported_and_the_chat_carries_on(client, llm):
    llm.replies["break"] = FakeRaise(RuntimeError("boom"))
    conversation_id = new_conversation(client)
    with client.websocket_connect(f"/ws/{conversation_id}") as ws:
        ws.receive_json()  # history
        ws.send_text("break")
        assert ws.receive_json() == {
            "type": "error",
            "message": "Something went wrong. Try again in a moment.",
        }
        ws.send_text("hi")
        assert reply_text(ws) == "Hello there"

    with client.websocket_connect(f"/ws/{conversation_id}") as ws:
        assert ws.receive_json()["messages"] == [
            {"role": "user", "content": "break"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "Hello there"},
        ]
