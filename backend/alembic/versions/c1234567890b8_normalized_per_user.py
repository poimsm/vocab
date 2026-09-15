"""words_normalized_per_user

Revision ID: c1234567890b8
Revises: bac6e1e744f8
Create Date: 2026-09-15 18:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c1234567890b8'
down_revision: Union[str, Sequence[str], None] = 'bac6e1e744f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # === WORDS TABLE ===
    # Drop the old global unique constraint on normalized
    op.drop_index('ix_words_normalized', table_name='words')

    # === EXAMPLES TABLE ===
    # Drop the global unique constraint on normalized
    op.drop_index('ix_examples_normalized', table_name='examples')

    # === BEST_OPTIONS TABLE ===
    # Drop the global unique constraint on normalized
    op.drop_index('ix_best_options_normalized', table_name='best_options')


def downgrade() -> None:
    """Downgrade schema."""
    # === WORDS TABLE ===

    # Restore the old global unique index on normalized
    op.create_index('ix_words_normalized', 'words', ['normalized'], unique=True)

    # === EXAMPLES TABLE ===
    # Restore the old global unique index on normalized
    op.create_index('ix_examples_normalized', 'examples', ['normalized'], unique=True)

    # === BEST_OPTIONS TABLE ===
    # Restore the old global unique index on normalized
    op.create_index('ix_best_options_normalized', 'best_options', ['normalized'], unique=True)
