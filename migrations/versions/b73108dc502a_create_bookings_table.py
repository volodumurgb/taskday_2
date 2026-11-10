"""Create bookings and prevent overlapping active reservations."""

import sqlalchemy as sa
from alembic import op

revision = "b73108dc502a"
down_revision = "f6cb21d341c5"


def upgrade() -> None:
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("desk_id", sa.Integer(), sa.ForeignKey("desks.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_cost", sa.Numeric(12, 2), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("ends_at > starts_at", name="ck_bookings_time_order"),
    )
    op.create_index("ix_bookings_desk_start", "bookings", ["desk_id", "starts_at"])
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE bookings ADD CONSTRAINT ex_bookings_desk_time
        EXCLUDE USING gist (
            desk_id WITH =,
            tstzrange(starts_at, ends_at, '[)') WITH &&
        ) WHERE (cancelled_at IS NULL)
        """
    )


def downgrade() -> None:
    op.drop_table("bookings")
