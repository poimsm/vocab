"""add is_in_use field to collocations

Revision ID: c1234567890b0
Revises: c1234567890af
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1234567890b0'
down_revision: Union[str, Sequence[str], None] = 'c1234567890af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('collocations', sa.Column('is_in_use', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index(op.f('ix_collocations_is_in_use'), 'collocations', ['is_in_use'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_collocations_is_in_use'), table_name='collocations')
    op.drop_column('collocations', 'is_in_use')
