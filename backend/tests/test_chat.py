import uuid

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.llm import FakeLLM, get_llm
from app.main import CONVERSATION_NOT_FOUND, app


@pytest.fixture
def llm():
    fake = FakeLLM(replies={"hi": "Hello there"})
    app.dependency_overrides[get_llm] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_llm)


@pytest.fixture
def client(llm):
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
        text = "".join(m["text"] for m in receive_reply(ws) if m["type"] == "delta")
        assert text == "You said: anything else"


def test_sends_the_whole_conversation_to_the_llm(client, llm):
    with client.websocket_connect(f"/ws/{new_conversation(client)}") as ws:
        ws.receive_json()  # history
        ws.send_text("hi")
        receive_reply(ws)
        ws.send_text("again")
        receive_reply(ws)

    assert llm.calls[-1] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hello there"},
        {"role": "user", "content": "again"},
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


def test_an_unknown_conversation_is_closed_as_not_found(client):
    with client.websocket_connect(f"/ws/{uuid.uuid4()}") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
    assert closed.value.code == CONVERSATION_NOT_FOUND
