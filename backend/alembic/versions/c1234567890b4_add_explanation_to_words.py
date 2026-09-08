"""add explanation field to words

Revision ID: c1234567890b4
Revises: c1234567890b3
Create Date: 2026-09-08 00:00:04.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1234567890b4'
down_revision: Union[str, Sequence[str], None] = 'c1234567890b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('words', sa.Column('explanation', sa.String(500), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('words', 'explanation')
