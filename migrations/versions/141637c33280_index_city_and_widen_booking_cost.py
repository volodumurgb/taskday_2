"""Index availability searches by city and widen the booking cost."""

import sqlalchemy as sa
from alembic import op

revision = "141637c33280"
down_revision = "e9331217aab0"


def upgrade() -> None:
    op.create_index("ix_locations_lower_city", "locations", [sa.text("lower(city)")])
    op.alter_column(
        "bookings", "total_cost", existing_type=sa.Numeric(12, 2), type_=sa.Numeric(20, 2)
    )


def downgrade() -> None:
    op.alter_column(
        "bookings", "total_cost", existing_type=sa.Numeric(20, 2), type_=sa.Numeric(12, 2)
    )
    op.drop_index("ix_locations_lower_city", table_name="locations")
