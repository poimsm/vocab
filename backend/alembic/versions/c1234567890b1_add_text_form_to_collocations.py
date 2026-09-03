"""add text_form field to collocations

Revision ID: c1234567890b1
Revises: c1234567890b0
Create Date: 2026-09-03 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1234567890b1'
down_revision: Union[str, Sequence[str], None] = 'c1234567890b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('collocations', sa.Column('text_form', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('collocations', 'text_form')
