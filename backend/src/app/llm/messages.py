"""Our own message format: what's stored, and what every LLM client translates to and from."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ToolCallPart(BaseModel):
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    arguments: dict[str, Any]


class ToolResultPart(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    call_id: str
    content: str
    is_error: bool = False


class ReasoningPart(BaseModel):
    """The model's reasoning. `opaque` is state only `provider` understands, such as a signature,
    so it's only ever sent back to that provider."""

    type: Literal["reasoning"] = "reasoning"
    provider: str
    text: str | None = None
    opaque: dict[str, Any] = Field(default_factory=dict)


class ProviderPart(BaseModel):
    """Content only one provider understands, kept so it can be sent back to that provider."""

    type: Literal["provider"] = "provider"
    provider: str
    data: dict[str, Any]


Part = Annotated[
    TextPart | ToolCallPart | ToolResultPart | ReasoningPart | ProviderPart,
    Field(discriminator="type"),
]


class Message(BaseModel):
    """One message in a conversation. Tool results have their own role, "tool"."""

    role: Literal["user", "assistant", "tool"]
    parts: list[Part]
    # Which provider and model wrote an assistant message.
    provider: str | None = None
    model: str | None = None
    # The provider's response exactly as received. Saved, but never read back or sent anywhere.
    raw: dict[str, Any] | None = Field(default=None, exclude=True)

    @classmethod
    def user(cls, text: str) -> "Message":
        return cls(role="user", parts=[TextPart(text=text)])

    @property
    def text(self) -> str:
        return "".join(part.text for part in self.parts if isinstance(part, TextPart))

    @property
    def tool_calls(self) -> list[ToolCallPart]:
        return [part for part in self.parts if isinstance(part, ToolCallPart)]

    @property
    def tool_results(self) -> list[ToolResultPart]:
        return [part for part in self.parts if isinstance(part, ToolResultPart)]
