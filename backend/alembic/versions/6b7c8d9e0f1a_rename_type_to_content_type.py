"""rename type to content_type in content_queue

Revision ID: 6b7c8d9e0f1a
Revises: 0b4e127c5aab
Create Date: 2026-10-03 10:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b7c8d9e0f1a'
down_revision: Union[str, Sequence[str], None] = '0b4e127c5aab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - rename type to content_type."""
    # Renombrar el campo type a content_type en la tabla content_queue
    op.alter_column('content_queue', 'type', new_column_name='content_type')


def downgrade() -> None:
    """Downgrade schema - rename content_type back to type."""
    # Revertir el cambio
    op.alter_column('content_queue', 'content_type', new_column_name='type')
