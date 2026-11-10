from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_admin
from app.db import Session
from app.locations import get_location_or_404
from app.models import Desk, Location

router = APIRouter(
    prefix="/locations/{location_id}/desks",
    tags=["desks"],
    dependencies=[Depends(require_admin)],
)


class DeskInput(BaseModel):
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    kind: Literal["open_space", "meeting_room", "private_office"]
    hourly_rate: Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class DeskResponse(DeskInput):
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_id: int


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_desk(location_id: int, payload: DeskInput) -> DeskResponse:
    """Create a workspace in the selected location."""
    async with Session.begin() as session:
        location = await session.get(Location, location_id, with_for_update=True)
        if location is None:
            raise HTTPException(status_code=404, detail="Location not found")

        desk = Desk(location_id=location.id, **payload.model_dump())
        session.add(desk)
        await session.flush()
        result = DeskResponse.model_validate(desk)

    return result


@router.get("")
async def list_desks(location_id: int) -> list[DeskResponse]:
    """List workspaces that belong to the selected location."""
    async with Session() as session:
        await get_location_or_404(session, location_id)
        statement = (
            select(Desk)
            .where(Desk.location_id == location_id)
            .order_by(Desk.id)
        )
        desks = await session.scalars(statement)
        return [DeskResponse.model_validate(desk) for desk in desks]


async def get_desk_or_404(
    session: AsyncSession, location_id: int, desk_id: int
) -> Desk:
    """Find a workspace within the location specified in the URL."""
    statement = select(Desk).where(
        Desk.id == desk_id,
        Desk.location_id == location_id,
    )
    desk = await session.scalar(statement)

    if desk is None:
        raise HTTPException(status_code=404, detail="Desk not found")

    return desk


@router.get("/{desk_id}")
async def read_desk(location_id: int, desk_id: int) -> DeskResponse:
    async with Session() as session:
        desk = await get_desk_or_404(session, location_id, desk_id)
        return DeskResponse.model_validate(desk)


@router.put("/{desk_id}")
async def update_desk(
    location_id: int, desk_id: int, payload: DeskInput
) -> DeskResponse:
    async with Session.begin() as session:
        desk = await get_desk_or_404(session, location_id, desk_id)
        desk.name = payload.name
        desk.kind = payload.kind
        desk.hourly_rate = payload.hourly_rate
        result = DeskResponse.model_validate(desk)

    return result


@router.delete("/{desk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_desk(location_id: int, desk_id: int) -> Response:
    async with Session.begin() as session:
        desk = await get_desk_or_404(session, location_id, desk_id)
        await session.delete(desk)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
