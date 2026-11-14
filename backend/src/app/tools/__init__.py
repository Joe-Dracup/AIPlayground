"""Tools Claude can call. To add one, write it in its own module and add it to get_tools."""

from app.db import Sessions
from app.tools.base import ToolRegistry
from app.tools.clock import get_time
from app.tools.places import place_tools


def get_tools(sessions: Sessions) -> ToolRegistry:
    return ToolRegistry([get_time, *place_tools(sessions)])
