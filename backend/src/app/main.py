import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.chat import TurnComplete, display_history, run_turn
from app.config import settings
from app.llm import ChatMessage, LLMClient, LLMError, TextDelta, get_llm
from app.store import PostgresConversationStore, get_store
from app.tools import get_tools
from app.tools.base import ToolRegistry

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
    tools: Annotated[ToolRegistry, Depends(get_tools)],
    store: Store,
):
    await websocket.accept()
    messages: list[ChatMessage] | None = await store.load(conversation_id)
    if messages is None:
        await websocket.close(code=CONVERSATION_NOT_FOUND, reason="Conversation not found")
        return

    # Send the history first, so a reconnecting client can rebuild the conversation.
    await websocket.send_json({"type": "history", "messages": display_history(messages)})

    try:
        while True:
            data = await websocket.receive_text()
            user_message: ChatMessage = {"role": "user", "content": data}
            messages.append(user_message)
            await store.append(conversation_id, user_message)

            try:
                async for event in run_turn(llm, tools, messages):
                    match event:
                        case TextDelta(text):
                            await websocket.send_json({"type": "delta", "text": text})
                        case TurnComplete(new_messages):
                            # Only saved once complete, so a reply cut off by an error is never
                            # stored.
                            messages.extend(new_messages)
                            await store.append(conversation_id, *new_messages)
                            await websocket.send_json({"type": "done"})
            except LLMError as e:
                # The partial reply isn't saved; the user's message stays, so they can try again.
                await websocket.send_json({"type": "error", "message": str(e)})
    except WebSocketDisconnect:
        # The client closed the tab or navigated away. Everything is already saved.
        pass
