"""add sale_price to subsidies

Revision ID: 20251028_add_sale_price
Revises: 82564d70969d
Create Date: 2025-10-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20251028_add_sale_price'
down_revision: Union[str, Sequence[str], None] = '82564d70969d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add sale_price column to subsidies."""
    op.add_column('subsidies', sa.Column('sale_price', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema: remove sale_price column from subsidies."""
    op.drop_column('subsidies', 'sale_price')
