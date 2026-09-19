"""Add updated_at to content_queue

Revision ID: c1234567890b9
Revises: c1234567890b8
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision: str = 'c1234567890b9'
down_revision: Union[str, Sequence[str], None] = '5d4e7c2b1a9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add updated_at column to content_queue
    op.add_column(
        'content_queue',
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
    )

    # Create index on updated_at for faster queries
    op.create_index('ix_content_queue_updated_at', 'content_queue', ['updated_at'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the index
    op.drop_index('ix_content_queue_updated_at', table_name='content_queue')

    # Remove updated_at column
    op.drop_column('content_queue', 'updated_at')
