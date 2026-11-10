import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db import Session
from app.models import Booking

logger = logging.getLogger("uvicorn.error")
REMINDER_LEAD_TIME = timedelta(hours=1)
POLL_INTERVAL_SECONDS = 1


async def claim_due_reminders(now: datetime) -> list[tuple[int, int]]:
    """Mark due, upcoming bookings so another worker cannot claim them again."""
    async with Session.begin() as session:
        statement = (
            select(Booking)
            .where(
                Booking.cancelled_at.is_(None),
                Booking.reminded_at.is_(None),
                Booking.starts_at > now,
                Booking.starts_at <= now + REMINDER_LEAD_TIME,
            )
            .order_by(Booking.starts_at, Booking.id)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
        bookings = await session.scalars(statement)
        claimed = []
        for booking in bookings:
            booking.reminded_at = now
            claimed.append((booking.id, booking.user_id))
    return claimed


async def run_reminders() -> None:
    """Log reminders as their scheduled time becomes due."""
    while True:
        try:
            for booking_id, user_id in await claim_due_reminders(
                datetime.now(timezone.utc)
            ):
                logger.info(
                    "Ваше бронювання починається через годину (booking_id=%s, user_id=%s)",
                    booking_id,
                    user_id,
                )
        except SQLAlchemyError:
            logger.exception("Unable to check booking reminders")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
