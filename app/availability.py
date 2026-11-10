from datetime import timezone
from hashlib import sha256
import json
import os
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import AwareDatetime, StringConstraints, TypeAdapter
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from redis.exceptions import RedisError
from sqlalchemy import func, select

from app.bookings import overlapping_bookings
from app.db import Session
from app.desks import DeskResponse
from app.models import Desk, Location

router = APIRouter(tags=["availability"])
CACHE_TTL_SECONDS = 20
desk_list = TypeAdapter(list[DeskResponse])


def create_cache() -> Redis:
    return Redis.from_url(
        os.getenv("REDIS_URL", "redis://redis:6379/0"),
        socket_timeout=0.5,
        socket_connect_timeout=0.5,
        retry=Retry(NoBackoff(), 0),
    )


@router.get("/availability")
async def find_available_desks(
    request: Request,
    city: Annotated[
        str, Query(), StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ],
    starts_at: AwareDatetime,
    ends_at: AwareDatetime,
) -> list[DeskResponse]:
    """List workspaces with no active booking in the requested window."""
    starts_at = starts_at.astimezone(timezone.utc)
    ends_at = ends_at.astimezone(timezone.utc)
    if ends_at <= starts_at:
        raise HTTPException(status_code=422, detail="End must be after start")

    cache: Redis = request.app.state.availability_cache
    key_data = json.dumps([city, starts_at.isoformat(), ends_at.isoformat()])
    key = "availability:v1:" + sha256(key_data.encode()).hexdigest()
    try:
        cached = await cache.get(key)
    except RedisError:
        cached = None
    if cached is not None:
        return desk_list.validate_json(cached)

    overlap = overlapping_bookings(Desk.id, starts_at, ends_at).exists()
    statement = (
        select(Desk)
        .join(Location, Desk.location_id == Location.id)
        .where(func.lower(Location.city) == func.lower(city), ~overlap)
        .order_by(Desk.id)
    )
    async with Session() as session:
        desks = await session.scalars(statement)
        result = [DeskResponse.model_validate(desk) for desk in desks]

    try:
        await cache.set(key, desk_list.dump_json(result), ex=CACHE_TTL_SECONDS)
    except RedisError:
        pass
    return result
