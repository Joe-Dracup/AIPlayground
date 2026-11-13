from typing import Annotated

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.llm import LLMClient, Message, get_llm

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello world"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


@app.websocket("/ws")
async def web_socket_endpoint(
    websocket: WebSocket, llm: Annotated[LLMClient, Depends(get_llm)]
):
    await websocket.accept()
    # One connection is one conversation, so the history lives as long as this function runs.
    messages: list[Message] = []
    try:
        while True:
            data = await websocket.receive_text()
            messages.append({"role": "user", "content": data})

            # Forward each chunk as it arrives, and keep the full reply for the history.
            reply = ""
            async for chunk in llm.stream_reply(messages):
                reply += chunk
                await websocket.send_json({"type": "delta", "text": chunk})

            messages.append({"role": "assistant", "content": reply})
            await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        # The client closed the tab or navigated away. Nothing to clean up yet.
        pass