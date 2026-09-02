"""add is_completed to collocations

Revision ID: c1234567890ac
Revises: c1234567890ab
Create Date: 2026-09-01 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1234567890ac'
down_revision: Union[str, Sequence[str], None] = 'c1234567890ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('collocations', sa.Column('is_completed', sa.Boolean(), nullable=False, server_default='false'))
    op.create_index(op.f('ix_collocations_is_completed'), 'collocations', ['is_completed'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_collocations_is_completed'), table_name='collocations')
    op.drop_column('collocations', 'is_completed')
