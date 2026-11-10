"""create desks table

Revision ID: f6cb21d341c5
Revises: 69fe3817ab7a
Create Date: 2026-11-10 15:10:54.303863

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f6cb21d341c5'
down_revision: Union[str, Sequence[str], None] = '69fe3817ab7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the desks table and its location index."""
    op.create_table(
        "desks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_desks_location_id", "desks", ["location_id"])


def downgrade() -> None:
    """Drop the desks table and its location index."""
    op.drop_index("ix_desks_location_id", table_name="desks")
    op.drop_table("desks")
