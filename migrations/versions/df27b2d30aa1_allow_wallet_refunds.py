"""Allow refunds even after the wallet has received more top-ups."""

import sqlalchemy as sa
from alembic import op

revision = "df27b2d30aa1"
down_revision = "b73108dc502a"


def upgrade() -> None:
    op.alter_column(
        "wallets", "balance", existing_type=sa.Numeric(12, 2), type_=sa.Numeric()
    )


def downgrade() -> None:
    op.alter_column(
        "wallets", "balance", existing_type=sa.Numeric(), type_=sa.Numeric(12, 2)
    )
