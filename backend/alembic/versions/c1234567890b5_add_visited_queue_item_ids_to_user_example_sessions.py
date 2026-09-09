"""add visited_queue_item_ids to user_example_sessions

Revision ID: c1234567890b6
Revises: c1234567890b5_base
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1234567890b6'
down_revision: Union[str, Sequence[str], None] = 'c1234567890b5_base'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('user_example_sessions', sa.Column('visited_queue_item_ids', sa.String(), nullable=False, server_default='[]'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_example_sessions', 'visited_queue_item_ids')
