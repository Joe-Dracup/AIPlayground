import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from app.llm import ToolCallPart, ToolResultPart, ToolSpec

logger = logging.getLogger(__name__)


class ToolError(Exception):
    """A tool couldn't do what was asked. The message goes back to the LLM, so it can adjust."""


@dataclass(frozen=True)
class Tool[Input: BaseModel]:
    """Something the LLM can ask us to run.

    The LLM sees the name, the description, and a JSON Schema generated from `input_model`, and
    uses them to decide when to call the tool and with what input.
    """

    name: str
    description: str
    input_model: type[Input]
    run: Callable[[Input], Awaitable[str]]

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.input_model.model_json_schema())


class ToolRegistry:
    """The tools the LLM can use, looked up by name."""

    # A tool taking longer than this counts as failed, so a stuck one can't hang the chat.
    TIMEOUT_SECONDS = 10

    def __init__(self, tools: list[Tool[Any]]):
        self._tools = {tool.name: tool for tool in tools}

    def specs(self) -> list[ToolSpec]:
        return [tool.spec() for tool in self._tools.values()]

    async def run(self, call: ToolCallPart) -> ToolResultPart:
        """Run a tool call, and return the result answering it.

        Never raises: a failure becomes an error result, which the LLM reads and reacts to.
        """
        try:
            content = await self._call(call.name, call.arguments)
            is_error = False
        except ToolError as e:
            content = str(e)
            is_error = True
        return ToolResultPart(call_id=call.id, content=content, is_error=is_error)

    async def _call(self, name: str, tool_input: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"There is no tool called {name!r}.")

        # The LLM's input is checked against the schema before the tool sees it.
        try:
            args = tool.input_model.model_validate(tool_input)
        except ValidationError as e:
            raise ToolError(f"Invalid input: {e}") from e

        try:
            async with asyncio.timeout(self.TIMEOUT_SECONDS):
                return await tool.run(args)
        except ToolError:
            raise
        except TimeoutError as e:
            raise ToolError(f"The tool took longer than {self.TIMEOUT_SECONDS} seconds.") from e
        except Exception as e:
            # Full details in the server log; the LLM only learns that it failed.
            logger.exception("Tool %s failed", name)
            raise ToolError("The tool failed unexpectedly.") from e
