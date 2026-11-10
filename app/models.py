from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Collect the table definitions used by the application."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), server_default="user")

class Wallet(Base):
    """Store the balance of a user's wallet."""

    __tablename__ = "wallets"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        primary_key=True,
    )
    balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        server_default="0.00",
    )

class Location(Base):
    """Represent a coworking site with a name, address, and city."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str] = mapped_column(String(250))
    city: Mapped[str] = mapped_column(String(100))