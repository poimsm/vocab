"""add is_marked to examples

Revision ID: c1234567890ae
Revises: c1234567890ad
Create Date: 2026-09-02 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1234567890ae'
down_revision: Union[str, Sequence[str], None] = 'c1234567890ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('examples', sa.Column('is_marked', sa.Boolean(), nullable=False, server_default='false'))
    op.create_index(op.f('ix_examples_is_marked'), 'examples', ['is_marked'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_examples_is_marked'), table_name='examples')
    op.drop_column('examples', 'is_marked')
