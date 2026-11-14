from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from app.tools.base import Tool, ToolError


class GetTimeInput(BaseModel):
    timezone: str = Field(
        default="UTC",
        description="IANA timezone name, e.g. Europe/London or America/New_York.",
    )


async def _get_time(args: GetTimeInput) -> str:
    try:
        zone = ZoneInfo(args.timezone)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise ToolError(
            f"Unknown timezone {args.timezone!r}. Use an IANA name like Europe/London."
        ) from e
    now = datetime.now(zone)
    return f"{now:%A %d %B %Y, %H:%M:%S} in {args.timezone} (UTC{now:%z})"


get_time = Tool(
    name="get_time",
    description=(
        "Get the current date and time in a timezone. Call this whenever the user asks about the "
        "current time, today's date or the day of the week, since you can't know them otherwise. "
        "If you don't know where the user is, use UTC and say that's what you used."
    ),
    input_model=GetTimeInput,
    run=_get_time,
)
