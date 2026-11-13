import pytest
from fastapi.testclient import TestClient

from app.llm import FakeLLM, get_llm
from app.main import app


@pytest.fixture
def llm():
    fake = FakeLLM(replies={"hi": "Hello there"})
    app.dependency_overrides[get_llm] = lambda: fake
    yield fake
    # Runs after the test, so one test's fake can't leak into the next.
    app.dependency_overrides.clear()


def receive_reply(ws) -> list[dict]:
    """Collect every message the server sends for one reply, up to and including "done"."""
    received = []
    while not received or received[-1]["type"] != "done":
        received.append(ws.receive_json())
    return received


def test_streams_the_matching_reply_in_chunks(llm):
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_text("hi")
        assert receive_reply(ws) == [
            {"type": "delta", "text": "Hello"},
            {"type": "delta", "text": " there"},
            {"type": "done"},
        ]


def test_echoes_messages_without_a_reply(llm):
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_text("anything else")
        text = "".join(m["text"] for m in receive_reply(ws) if m["type"] == "delta")
        assert text == "You said: anything else"


def test_sends_the_whole_conversation_to_the_llm(llm):
    with TestClient(app).websocket_connect("/ws") as ws:
        ws.send_text("hi")
        receive_reply(ws)
        ws.send_text("again")
        receive_reply(ws)

    assert llm.calls[-1] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "Hello there"},
        {"role": "user", "content": "again"},
    ]
