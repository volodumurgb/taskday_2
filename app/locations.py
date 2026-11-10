from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import Session
from app.models import Location

router = APIRouter(
    prefix="/locations",
    tags=["locations"],
    dependencies=[Depends(require_admin)],
)


class LocationInput(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=250)]
    city: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class LocationResponse(LocationInput):
    model_config = ConfigDict(from_attributes=True)

    id: int

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_location(payload: LocationInput) -> LocationResponse:
    """Create a location and return it with its database-generated ID."""
    async with Session.begin() as session:
        location = Location(**payload.model_dump())
        session.add(location)
        await session.flush()
        result = LocationResponse.model_validate(location)

    return result


@router.get("")
async def list_locations() -> list[LocationResponse]:
    """Return locations in ascending ID order."""
    async with Session() as session:
        locations = await session.scalars(select(Location).order_by(Location.id))
        return [LocationResponse.model_validate(location) for location in locations]


async def get_location_or_404(
    session: AsyncSession,
    location_id: int,
) -> Location:
    """Load a location or end the request with a 404 response."""
    location = await session.get(Location, location_id)
    if location is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )
    return location


@router.get("/{location_id}")
async def read_location(location_id: int) -> LocationResponse:
    async with Session() as session:
        location = await get_location_or_404(session, location_id)
        return LocationResponse.model_validate(location)

@router.put("/{location_id}")
async def update_location(
    location_id: int,
    payload: LocationInput,
) -> LocationResponse:
    """Replace the name, address, and city of an existing location."""
    async with Session.begin() as session:
        location = await get_location_or_404(session, location_id)
        location.name = payload.name
        location.address = payload.address
        location.city = payload.city
        result = LocationResponse.model_validate(location)

    return result


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(location_id: int) -> Response:
    async with Session.begin() as session:
        location = await get_location_or_404(session, location_id)
        await session.delete(location)

    return Response(status_code=status.HTTP_204_NO_CONTENT)