from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), server_default="user")


class Wallet(Base):
    __tablename__ = "wallets"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        primary_key=True,
    )
    balance: Mapped[Decimal] = mapped_column(
        Numeric(),
        server_default="0.00",
    )


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(250))
    city: Mapped[str] = mapped_column(String(100))

    __table_args__ = (Index("ix_locations_lower_city", func.lower(city)),)


class Desk(Base):
    __tablename__ = "desks"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("locations.id"),
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(30))
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_bookings_time_order"),
        Index("ix_bookings_desk_start", "desk_id", "starts_at"),
        Index(
            "ix_bookings_pending_reminders",
            "starts_at",
            postgresql_where=text("cancelled_at IS NULL AND reminded_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    desk_id: Mapped[int] = mapped_column(ForeignKey("desks.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
