"""create locations table

Revision ID: 69fe3817ab7a
Revises: 83188c5bbe15
Create Date: 2026-11-10 14:36:03.536143

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '69fe3817ab7a'
down_revision: Union[str, Sequence[str], None] = '83188c5bbe15'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('locations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('address', sa.String(length=250), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('locations')
