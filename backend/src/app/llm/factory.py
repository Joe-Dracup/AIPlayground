from functools import cache

import anthropic

from app.config import settings
from app.llm.anthropic_llm import AnthropicLLM
from app.llm.base import LLMClient
from app.llm.fake import FAKE_REPLIES, FakeLLM


# Cached so every chat shares one client (and its connection pool): a singleton.
@cache
def _anthropic_client(api_key: str) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=api_key)


def get_llm() -> LLMClient:
    if settings.anthropic_api_key is not None:
        client = _anthropic_client(settings.anthropic_api_key.get_secret_value())
        return AnthropicLLM(client, model=settings.anthropic_model)

    return FakeLLM(replies=FAKE_REPLIES, delay=0.08)
