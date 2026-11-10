"""Track booking reminders and index upcoming unsent reminders."""

import sqlalchemy as sa
from alembic import op

revision = "e9331217aab0"
down_revision = "df27b2d30aa1"


def upgrade() -> None:
    op.add_column("bookings", sa.Column("reminded_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_bookings_pending_reminders",
        "bookings",
        ["starts_at"],
        postgresql_where=sa.text("cancelled_at IS NULL AND reminded_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_bookings_pending_reminders", table_name="bookings")
    op.drop_column("bookings", "reminded_at")
