import json
from dataclasses import asdict
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.places.queries import find_places_by_name, search_places_near
from app.places.vocabulary import TAG_DESCRIPTIONS, Category, Tag
from app.tools.base import Tool, ToolError


class FindPlaceInput(BaseModel):
    query: str = Field(description="All or part of the place's name, e.g. 'Piccadilly'.")


class SearchPlacesInput(BaseModel):
    near_place_id: int = Field(description="The id of the place to search around, from find_place.")
    within_m: int = Field(
        default=1000, ge=1, le=10000, description="How far away places can be, in metres."
    )
    category: Category | None = Field(default=None, description="Only places of this kind.")
    tags: list[Tag] = Field(
        default_factory=list, description="Only places that have all of these characteristics."
    )
    limit: int = Field(default=10, ge=1, le=25, description="The most places to return.")


_TAG_MEANINGS = "\n".join(f"- {tag}: {meaning}" for tag, meaning in TAG_DESCRIPTIONS.items())


def place_tools(sessions: async_sessionmaker[AsyncSession]) -> list[Tool[Any]]:
    async def find_place(args: FindPlaceInput) -> str:
        async with sessions() as session:
            places = await find_places_by_name(session, args.query)
        return _to_json(places)

    async def search_places(args: SearchPlacesInput) -> str:
        async with sessions() as session:
            places = await search_places_near(
                session,
                args.near_place_id,
                within_m=args.within_m,
                category=args.category,
                tags=args.tags,
                limit=args.limit,
            )
        if places is None:
            raise ToolError(
                f"There's no place with id {args.near_place_id}. Look it up with find_place."
            )
        return _to_json(places)

    return [
        Tool(
            name="find_place",
            description=(
                "Look up places by name, to get their ids. Call this first to find the place the "
                "user wants to search around (e.g. a station), or to check if a place is known. "
                "Returns up to 5 matches as JSON. If several match, pick the one the user most "
                "likely means, or ask them. Only covers central Manchester for now."
            ),
            input_model=FindPlaceInput,
            run=find_place,
        ),
        Tool(
            name="search_places",
            description=(
                "Find places within a distance of another place, nearest first, e.g. "
                "'a dog-friendly pub near Piccadilly'. Get near_place_id from find_place first. "
                "Returns JSON, with each place's straight-line distance in metres. Only covers "
                "central Manchester for now. The tags mean:\n" + _TAG_MEANINGS
            ),
            input_model=SearchPlacesInput,
            run=search_places,
        ),
    ]


def _to_json(places: list[Any]) -> str:
    return json.dumps([asdict(place) for place in places], ensure_ascii=False)
