import asyncio

import pytest
from pydantic import BaseModel

from app.tools.base import Tool, ToolError, ToolRegistry
from app.tools.clock import get_time

# Runs this file's async tests on an event loop, using the pytest plugin that comes with anyio.
pytestmark = pytest.mark.anyio


def tool_use(name: str, tool_input: dict) -> dict:
    return {"type": "tool_use", "id": "toolu_1", "name": name, "input": tool_input}


class NoInput(BaseModel):
    pass


def tool_running(run) -> ToolRegistry:
    return ToolRegistry([Tool(name="test", description="", input_model=NoInput, run=run)])


async def test_get_time_returns_the_time_in_the_timezone():
    result = await ToolRegistry([get_time]).run(tool_use("get_time", {"timezone": "Asia/Tokyo"}))
    assert result["type"] == "tool_result"
    assert result["tool_use_id"] == "toolu_1"
    assert result["is_error"] is False
    assert result["content"].endswith("in Asia/Tokyo (UTC+0900)")


async def test_get_time_defaults_to_utc():
    result = await ToolRegistry([get_time]).run(tool_use("get_time", {}))
    assert result["content"].endswith("in UTC (UTC+0000)")


async def test_an_unknown_timezone_is_an_error_claude_can_read():
    result = await ToolRegistry([get_time]).run(tool_use("get_time", {"timezone": "Mars/Base"}))
    assert result["is_error"] is True
    assert result["content"].startswith("Unknown timezone 'Mars/Base'")


async def test_input_that_doesnt_match_the_schema_is_an_error():
    result = await ToolRegistry([get_time]).run(tool_use("get_time", {"timezone": 42}))
    assert result["is_error"] is True
    assert result["content"].startswith("Invalid input")


async def test_an_unknown_tool_is_an_error():
    result = await ToolRegistry([get_time]).run(tool_use("launch_rocket", {}))
    assert result["is_error"] is True
    assert result["content"] == "There is no tool called 'launch_rocket'."


async def test_an_unexpected_failure_is_hidden_from_claude():
    async def crash(args: NoInput) -> str:
        raise RuntimeError("database password is hunter2")

    result = await tool_running(crash).run(tool_use("test", {}))
    assert result["is_error"] is True
    assert result["content"] == "The tool failed unexpectedly."


async def test_a_tool_error_message_is_passed_on():
    async def refuse(args: NoInput) -> str:
        raise ToolError("Nothing found near there.")

    result = await tool_running(refuse).run(tool_use("test", {}))
    assert result["content"] == "Nothing found near there."


async def test_a_slow_tool_times_out(monkeypatch):
    monkeypatch.setattr(ToolRegistry, "TIMEOUT_SECONDS", 0.01)

    async def hang(args: NoInput) -> str:
        await asyncio.sleep(1)
        return "too late"

    result = await tool_running(hang).run(tool_use("test", {}))
    assert result["is_error"] is True
    assert result["content"] == "The tool took longer than 0.01 seconds."


def test_definitions_include_a_schema_generated_from_the_input_model():
    [definition] = ToolRegistry([get_time]).definitions()
    assert definition["name"] == "get_time"
    assert definition["input_schema"]["type"] == "object"
    assert definition["input_schema"]["properties"]["timezone"]["type"] == "string"
