"""rename content_queue to learning_path_queue

Revision ID: 7c8d9e0f2b3c
Revises: 6b7c8d9e0f1a
Create Date: 2026-10-03 10:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7c8d9e0f2b3c'
down_revision: Union[str, Sequence[str], None] = '6b7c8d9e0f1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - rename content_queue to learning_path_queue."""
    # Renombrar la tabla content_queue a learning_path_queue
    op.rename_table('content_queue', 'learning_path_queue')


def downgrade() -> None:
    """Downgrade schema - rename learning_path_queue back to content_queue."""
    # Revertir el cambio
    op.rename_table('learning_path_queue', 'content_queue')
