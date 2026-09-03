"""add favorited_at to words and learned_at to word_statistics

Revision ID: c1234567890af
Revises: c1234567890ae
Create Date: 2026-09-02 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1234567890af'
down_revision: Union[str, Sequence[str], None] = 'c1234567890ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('words', sa.Column('favorited_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_words_favorited_at'), 'words', ['favorited_at'], unique=False)

    op.add_column('word_statistics', sa.Column('learned_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_word_statistics_learned_at'), 'word_statistics', ['learned_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_words_favorited_at'), table_name='words')
    op.drop_column('words', 'favorited_at')

    op.drop_index(op.f('ix_word_statistics_learned_at'), table_name='word_statistics')
    op.drop_column('word_statistics', 'learned_at')
