"""Tools Claude can call. To add one, write it in its own module and add it to TOOLS."""

from app.tools.base import ToolRegistry
from app.tools.clock import get_time

TOOLS = ToolRegistry([get_time])


def get_tools() -> ToolRegistry:
    return TOOLS
