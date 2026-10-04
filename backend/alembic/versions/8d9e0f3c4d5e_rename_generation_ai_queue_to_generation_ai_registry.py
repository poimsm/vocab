"""rename generation_ai_queue to generation_ai_registry

Revision ID: 8d9e0f3c4d5e
Revises: 7c8d9e0f2b3c
Create Date: 2026-10-03 10:14:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d9e0f3c4d5e'
down_revision: Union[str, Sequence[str], None] = '7c8d9e0f2b3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - rename generation_ai_queue to generation_ai_registry."""
    # Renombrar la tabla generation_ai_queue a generation_ai_registry
    op.rename_table('generation_ai_queue', 'generation_ai_registry')


def downgrade() -> None:
    """Downgrade schema - rename generation_ai_registry back to generation_ai_queue."""
    # Revertir el cambio
    op.rename_table('generation_ai_registry', 'generation_ai_queue')
