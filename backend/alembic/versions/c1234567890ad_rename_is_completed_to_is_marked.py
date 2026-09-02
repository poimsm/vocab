"""rename is_completed to is_marked in collocations

Revision ID: c1234567890ad
Revises: c1234567890ac
Create Date: 2026-09-02 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1234567890ad'
down_revision: Union[str, Sequence[str], None] = 'c1234567890ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rename the column
    op.alter_column('collocations', 'is_completed', new_column_name='is_marked')
    # Rename the index
    op.drop_index(op.f('ix_collocations_is_completed'), table_name='collocations')
    op.create_index(op.f('ix_collocations_is_marked'), 'collocations', ['is_marked'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Rename back to is_completed
    op.drop_index(op.f('ix_collocations_is_marked'), table_name='collocations')
    op.alter_column('collocations', 'is_marked', new_column_name='is_completed')
    op.create_index(op.f('ix_collocations_is_completed'), 'collocations', ['is_completed'], unique=False)
