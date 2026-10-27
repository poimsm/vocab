"""Add target fields to words table

Revision ID: add_target_fields
Revises: e9b979867c02
Create Date: 2026-10-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'add_target_fields'
down_revision: Union[str, Sequence[str], None] = 'e9b979867c02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add target fields to words table."""
    op.add_column('words', sa.Column('target_word', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True))
    op.add_column('words', sa.Column('target_synonym', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=True))
    op.add_column('words', sa.Column('target_explanation', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True))


def downgrade() -> None:
    """Downgrade schema - Remove target fields from words table."""
    op.drop_column('words', 'target_explanation')
    op.drop_column('words', 'target_synonym')
    op.drop_column('words', 'target_word')
