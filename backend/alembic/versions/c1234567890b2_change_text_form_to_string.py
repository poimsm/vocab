"""change text_form from JSON to string

Revision ID: c1234567890b2
Revises: c1234567890b1
Create Date: 2026-09-03 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1234567890b2'
down_revision: Union[str, Sequence[str], None] = 'c1234567890b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop the JSON column and recreate as string
    op.drop_column('collocations', 'text_form')
    op.add_column('collocations', sa.Column('text_form', sa.String(255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Revert to JSON column
    op.drop_column('collocations', 'text_form')
    op.add_column('collocations', sa.Column('text_form', sa.JSON(), nullable=True))
