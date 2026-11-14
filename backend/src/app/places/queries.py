from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Place
from app.places.vocabulary import Category, Tag


@dataclass(frozen=True)
class FoundPlace:
    id: int
    name: str
    category: str
    tags: list[str]


@dataclass(frozen=True)
class NearbyPlace(FoundPlace):
    distance_m: int


async def find_places_by_name(
    session: AsyncSession, query: str, limit: int = 5
) -> list[FoundPlace]:
    """Places whose name contains `query`, ignoring case."""
    result = await session.execute(
        select(Place.id, Place.name, Place.category, Place.tags)
        .where(Place.name.icontains(query, autoescape=True))
        .order_by(Place.name)
        .limit(limit)
    )
    return [FoundPlace(**row._asdict()) for row in result]


async def search_places_near(
    session: AsyncSession,
    origin_id: int,
    within_m: float,
    category: Category | None = None,
    tags: list[Tag] | None = None,
    limit: int = 10,
) -> list[NearbyPlace] | None:
    """Places within `within_m` metres of another place, nearest first.

    Optionally only those in `category`, or having every one of `tags`. Returns None if there's
    no place with id `origin_id`.
    """
    if await session.scalar(select(Place.id).where(Place.id == origin_id)) is None:
        return None

    origin = select(Place.location).where(Place.id == origin_id).scalar_subquery()
    distance = func.ST_Distance(Place.location, origin)

    query = select(
        Place.id, Place.name, Place.category, Place.tags, distance.label("distance_m")
    ).where(Place.id != origin_id, func.ST_DWithin(Place.location, origin, within_m))
    if category is not None:
        query = query.where(Place.category == category)
    if tags:
        query = query.where(Place.tags.contains(tags))

    result = await session.execute(query.order_by(distance).limit(limit))
    return [NearbyPlace(**row._asdict() | {"distance_m": round(row.distance_m)}) for row in result]
