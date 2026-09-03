"""add in_use_at field to collocations

Revision ID: c1234567890b3
Revises: c1234567890b2
Create Date: 2026-09-03 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1234567890b3'
down_revision: Union[str, Sequence[str], None] = 'c1234567890b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('collocations', sa.Column('in_use_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_collocations_in_use_at'), 'collocations', ['in_use_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_collocations_in_use_at'), table_name='collocations')
    op.drop_column('collocations', 'in_use_at')
