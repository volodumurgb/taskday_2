from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from app.auth import get_current_user
from app.db import Session
from app.models import Booking, Desk, User, Wallet

router = APIRouter(prefix="/bookings", tags=["bookings"])


class BookingInput(BaseModel):
    desk_id: Annotated[int, Field(gt=0, le=2_147_483_647)]
    starts_at: AwareDatetime
    ends_at: AwareDatetime


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    desk_id: int
    starts_at: datetime
    ends_at: datetime
    total_cost: Decimal
    cancelled_at: datetime | None


def calculate_cost(
    hourly_rate: Decimal, starts_at: datetime, ends_at: datetime
) -> Decimal:
    """Charge proportionally to elapsed time and round half up to cents."""
    duration = ends_at - starts_at
    seconds = Decimal(duration.days * 86400 + duration.seconds)
    seconds += Decimal(duration.microseconds).scaleb(-6)
    return (hourly_rate * seconds / 3600).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def overlapping_bookings(desk_id, starts_at: datetime, ends_at: datetime):
    """Select active bookings intersecting the half-open time window."""
    return select(Booking.id).where(
        Booking.desk_id == desk_id,
        Booking.cancelled_at.is_(None),
        Booking.starts_at < ends_at,
        Booking.ends_at > starts_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingInput,
    user: Annotated[User, Depends(get_current_user)],
) -> BookingResponse:
    """Reserve an available workspace and charge its cost atomically."""
    starts_at = payload.starts_at.astimezone(timezone.utc)
    ends_at = payload.ends_at.astimezone(timezone.utc)
    if ends_at <= starts_at:
        raise HTTPException(status_code=422, detail="End must be after start")

    try:
        async with Session.begin() as session:
            desk = await session.get(Desk, payload.desk_id, with_for_update=True)
            if desk is None:
                raise HTTPException(status_code=404, detail="Desk not found")
            if starts_at <= datetime.now(timezone.utc):
                raise HTTPException(status_code=422, detail="Start must be in the future")

            overlap = overlapping_bookings(desk.id, starts_at, ends_at).limit(1)
            if await session.scalar(overlap) is not None:
                raise HTTPException(status_code=409, detail="Desk is already booked")

            cost = calculate_cost(desk.hourly_rate, starts_at, ends_at)
            debit = (
                update(Wallet)
                .where(Wallet.user_id == user.id, Wallet.balance >= cost)
                .values(balance=Wallet.balance - cost)
                .returning(Wallet.user_id)
            )
            if await session.scalar(debit) is None:
                raise HTTPException(status_code=409, detail="Insufficient funds")

            booking = Booking(
                user_id=user.id,
                desk_id=desk.id,
                starts_at=starts_at,
                ends_at=ends_at,
                total_cost=cost,
            )
            session.add(booking)
            await session.flush()
            result = BookingResponse.model_validate(booking)
    except IntegrityError as exc:
        if getattr(exc.orig, "sqlstate", None) != "23P01":
            raise
        raise HTTPException(status_code=409, detail="Desk is already booked") from exc

    return result


@router.post("/{booking_id}/cancel")
async def cancel_booking(
    booking_id: Annotated[int, Path(gt=0, le=2_147_483_647)],
    user: Annotated[User, Depends(get_current_user)],
) -> BookingResponse:
    """Cancel the owner's upcoming booking and refund the original charge."""
    async with Session.begin() as session:
        statement = (
            select(Booking)
            .where(Booking.id == booking_id, Booking.user_id == user.id)
            .with_for_update()
        )
        booking = await session.scalar(statement)
        if booking is None:
            raise HTTPException(status_code=404, detail="Booking not found")
        if booking.cancelled_at is not None:
            raise HTTPException(status_code=409, detail="Booking is already cancelled")

        now = datetime.now(timezone.utc)
        if booking.starts_at <= now:
            raise HTTPException(status_code=409, detail="Booking has already started")

        refund = (
            update(Wallet)
            .where(Wallet.user_id == user.id)
            .values(balance=Wallet.balance + booking.total_cost)
            .returning(Wallet.user_id)
        )
        if await session.scalar(refund) is None:
            raise HTTPException(status_code=409, detail="Wallet not found")

        booking.cancelled_at = now
        result = BookingResponse.model_validate(booking)

    return result
