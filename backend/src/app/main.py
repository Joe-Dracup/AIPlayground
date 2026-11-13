import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.llm import ChatMessage, LLMClient, get_llm
from app.store import PostgresConversationStore, get_store

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

Store = Annotated[PostgresConversationStore, Depends(get_store)]

# Websocket close code for an unknown conversation. 4000-4999 are free for apps to use.
CONVERSATION_NOT_FOUND = 4404


@app.get("/")
def read_root():
    return {"message": "Hello world"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


class ConversationCreated(BaseModel):
    id: uuid.UUID


@app.post("/conversations", status_code=201)
async def create_conversation(store: Store) -> ConversationCreated:
    return ConversationCreated(id=await store.create())


@app.websocket("/ws/{conversation_id}")
async def web_socket_endpoint(
    websocket: WebSocket,
    conversation_id: uuid.UUID,
    llm: Annotated[LLMClient, Depends(get_llm)],
    store: Store,
):
    await websocket.accept()
    messages: list[ChatMessage] | None = await store.load(conversation_id)
    if messages is None:
        await websocket.close(code=CONVERSATION_NOT_FOUND, reason="Conversation not found")
        return

    # Send the history first, so a reconnecting client can rebuild the conversation.
    await websocket.send_json({"type": "history", "messages": messages})

    try:
        while True:
            data = await websocket.receive_text()
            user_message: ChatMessage = {"role": "user", "content": data}
            messages.append(user_message)
            await store.append(conversation_id, user_message)

            # Forward each chunk as it arrives, and keep the full reply for the history.
            reply = ""
            async for chunk in llm.stream_reply(messages):
                reply += chunk
                await websocket.send_json({"type": "delta", "text": chunk})

            # Only saved once complete, so a reply cut off by an error is never stored.
            assistant_message: ChatMessage = {"role": "assistant", "content": reply}
            messages.append(assistant_message)
            await store.append(conversation_id, assistant_message)
            await websocket.send_json({"type": "done"})
    except WebSocketDisconnect:
        # The client closed the tab or navigated away. Everything is already saved.
        pass
