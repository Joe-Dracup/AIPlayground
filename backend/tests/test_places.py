import json
from typing import get_args

import pytest
from fastapi.testclient import TestClient

from app.llm import FakeLLM, FakeToolCall, ToolCallPart, get_llm
from app.main import app
from app.places.queries import find_places_by_name, search_places_near
from app.places.vocabulary import TAG_DESCRIPTIONS, Tag
from app.tools.base import ToolRegistry
from app.tools.places import place_tools

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("seeded")]


async def place_id(sessions, name: str) -> int:
    async with sessions() as session:
        [place] = await find_places_by_name(session, name)
    return place.id


async def names_near(sessions, name: str, **filters) -> list[str]:
    async with sessions() as session:
        places = await search_places_near(session, await place_id(sessions, name), **filters)
    return [place.name for place in places]


async def test_finds_places_by_part_of_their_name_ignoring_case(sessions):
    async with sessions() as session:
        places = await find_places_by_name(session, "GARDENS")
    assert [place.name for place in places] == ["Cathedral Gardens", "Piccadilly Gardens"]


async def test_finding_by_name_returns_at_most_the_limit(sessions):
    async with sessions() as session:
        assert len(await find_places_by_name(session, "a")) == 5


async def test_wildcards_in_a_name_search_are_matched_literally(sessions):
    async with sessions() as session:
        assert await find_places_by_name(session, "%") == []


async def test_searches_nearest_first_without_the_origin(sessions):
    assert await names_near(sessions, "Manchester Piccadilly", within_m=1000) == [
        "Mayfield Park",
        "Takk",
        "Piccadilly Gardens",
        "Port Street Beer House",
        "Ezra & Gil",
        "Manchester Oxford Road",
        "Rudy's Pizza Ancoats",
        "Federal Café",
    ]


async def test_search_includes_distances_in_whole_metres(sessions):
    origin = await place_id(sessions, "Manchester Piccadilly")
    async with sessions() as session:
        [nearest] = await search_places_near(session, origin, within_m=1000, limit=1)
    assert nearest.name == "Mayfield Park"
    assert isinstance(nearest.distance_m, int)
    assert 250 < nearest.distance_m < 400


async def test_search_filters_by_category(sessions):
    assert await names_near(sessions, "Manchester Piccadilly", within_m=1000, category="pub") == [
        "Port Street Beer House"
    ]


async def test_search_only_returns_places_with_every_tag(sessions):
    assert await names_near(
        sessions, "Manchester Piccadilly", within_m=2000, tags=["wifi", "dog_friendly"]
    ) == ["Ezra & Gil"]


async def test_search_returns_at_most_the_limit(sessions):
    assert await names_near(sessions, "Manchester Piccadilly", within_m=1000, limit=2) == [
        "Mayfield Park",
        "Takk",
    ]


async def test_searching_around_an_unknown_place_returns_none(sessions):
    async with sessions() as session:
        assert await search_places_near(session, 999_999, within_m=1000) is None


def tool_use(name: str, tool_input: dict) -> ToolCallPart:
    return ToolCallPart(id="call_1", name=name, arguments=tool_input)


async def test_find_place_tool_returns_matches_as_json(sessions):
    result = await ToolRegistry(place_tools(sessions)).run(
        tool_use("find_place", {"query": "piccadilly"})
    )
    assert result.is_error is False
    assert [place["name"] for place in json.loads(result.content)] == [
        "Manchester Piccadilly",
        "Piccadilly Gardens",
    ]


async def test_search_places_tool_returns_matches_as_json(sessions):
    origin = await place_id(sessions, "Manchester Piccadilly")
    result = await ToolRegistry(place_tools(sessions)).run(
        tool_use("search_places", {"near_place_id": origin, "category": "pub"})
    )
    [pub] = json.loads(result.content)
    assert pub == {
        "id": pub["id"],
        "name": "Port Street Beer House",
        "category": "pub",
        "tags": ["real_ale"],
        "distance_m": pub["distance_m"],
    }


async def test_search_places_tool_reports_an_unknown_place(sessions):
    result = await ToolRegistry(place_tools(sessions)).run(
        tool_use("search_places", {"near_place_id": 999_999})
    )
    assert result.is_error is True
    assert result.content == "There's no place with id 999999. Look it up with find_place."


def test_every_tag_has_a_description():
    assert set(TAG_DESCRIPTIONS) == set(get_args(Tag))


def test_chat_chains_find_place_into_search_places():
    fake = FakeLLM(
        replies={
            "pubs near piccadilly": [
                FakeToolCall("find_place", {"query": "Manchester Piccadilly"}),
                FakeToolCall(
                    "search_places",
                    lambda found: {"near_place_id": json.loads(found)[0]["id"], "category": "pub"},
                ),
            ]
        }
    )
    app.dependency_overrides[get_llm] = lambda: fake
    try:
        client = TestClient(app)
        conversation_id = client.post("/conversations").json()["id"]
        with client.websocket_connect(f"/ws/{conversation_id}") as ws:
            ws.receive_json()  # history
            ws.send_text("pubs near piccadilly")
            text = ""
            while (message := ws.receive_json())["type"] == "delta":
                text += message["text"]
    finally:
        app.dependency_overrides.pop(get_llm)

    assert message == {"type": "done"}
    assert "Port Street Beer House" in text
