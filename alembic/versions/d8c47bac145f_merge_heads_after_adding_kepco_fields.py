"""merge heads after adding kepco fields

Revision ID: d8c47bac145f
Revises: 0f42d4f96fa6, 20251020_add_kepco_fields
Create Date: 2025-10-20 17:32:45.204261

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8c47bac145f'
down_revision: Union[str, Sequence[str], None] = ('0f42d4f96fa6', '20251020_add_kepco_fields')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
