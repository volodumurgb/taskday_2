"""create wallets table

Revision ID: 83188c5bbe15
Revises: d5ba48d62ada
Create Date: 2026-11-10 13:52:48.199153

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '83188c5bbe15'
down_revision: Union[str, Sequence[str], None] = 'd5ba48d62ada'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('wallets',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('balance', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('wallets')
