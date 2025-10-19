"""merge heads 9508604ce511 + c1d2e3f4add

Revision ID: 0f42d4f96fa6
Revises: 9508604ce511, c1d2e3f4add
Create Date: 2025-10-20 00:26:40.525248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f42d4f96fa6'
down_revision: Union[str, Sequence[str], None] = ('9508604ce511', 'c1d2e3f4add')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
