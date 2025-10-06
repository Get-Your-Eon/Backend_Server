"""Add unique constraint to Charger table

Revision ID: b7a145511e70
Revises: 60afb71f58fe
Create Date: 2025-10-06 02:24:15.779401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7a145511e70'
down_revision: Union[str, Sequence[str], None] = '60afb71f58fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
