"""Sample places around Manchester city centre, to build and try search against before there's
an import job. Run with `uv run python -m app.seed`. Running it again replaces them.

The places are real, but the locations are approximate and the tags are made up for testing:
they aren't facts about these places.
"""

import asyncio
import re

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Session, engine
from app.models import Place
from app.places.vocabulary import Category, Tag

SOURCE = "seed"

# name, category, latitude, longitude, tags
PLACES: list[tuple[str, Category, float, float, list[Tag]]] = [
    ("Manchester Piccadilly", "station", 53.4774, -2.2309, []),
    ("Manchester Victoria", "station", 53.4875, -2.2425, []),
    ("Manchester Oxford Road", "station", 53.4740, -2.2420, []),
    ("Deansgate", "station", 53.4743, -2.2510, []),
    ("Piccadilly Gardens", "park", 53.4810, -2.2367, ["dog_friendly"]),
    ("Mayfield Park", "park", 53.4760, -2.2265, ["dog_friendly", "playground"]),
    ("Cathedral Gardens", "park", 53.4855, -2.2430, []),
    ("Castlefield Viaduct", "park", 53.4747, -2.2580, ["step_free"]),
    ("Whitworth Park", "park", 53.4600, -2.2290, ["dog_friendly", "playground"]),
    ("The Briton's Protection", "pub", 53.4762, -2.2477, ["real_ale", "dog_friendly"]),
    ("Sinclair's Oyster Bar", "pub", 53.4839, -2.2444, ["outdoor_seating"]),
    ("The Peveril of the Peak", "pub", 53.4757, -2.2460, ["real_ale"]),
    ("The Marble Arch", "pub", 53.4905, -2.2335, ["real_ale", "dog_friendly"]),
    ("Port Street Beer House", "pub", 53.4835, -2.2330, ["real_ale"]),
    ("Federal Café", "cafe", 53.4848, -2.2380, ["wifi", "vegan_options"]),
    ("Pot Kettle Black", "cafe", 53.4818, -2.2462, ["wifi"]),
    ("Ezra & Gil", "cafe", 53.4834, -2.2349, ["wifi", "dog_friendly"]),
    ("Takk", "cafe", 53.4820, -2.2305, ["wifi", "vegan_options"]),
    ("Mackie Mayor", "restaurant", 53.4874, -2.2373, ["vegan_options", "step_free"]),
    ("Hawksmoor", "restaurant", 53.4795, -2.2490, []),
    ("Rudy's Pizza Ancoats", "restaurant", 53.4848, -2.2268, ["vegan_options"]),
]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


async def seed(session: AsyncSession) -> int:
    """Replace the seeded places with PLACES. Returns how many there are."""
    rows = [
        {
            "source": SOURCE,
            "source_id": _slug(name),
            "name": name,
            "category": category,
            "location": f"SRID=4326;POINT({longitude} {latitude})",
            "tags": tags,
            "source_data": {},
        }
        for name, category, latitude, longitude, tags in PLACES
    ]
    await session.execute(delete(Place).where(Place.source == SOURCE))
    await session.execute(insert(Place), rows)
    return len(rows)


async def main() -> None:
    async with Session() as session, session.begin():
        count = await seed(session)
    await engine.dispose()
    print(f"Seeded {count} places.")


if __name__ == "__main__":
    asyncio.run(main())
