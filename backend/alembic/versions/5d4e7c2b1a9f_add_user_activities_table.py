"""Add user activities table for activity tracking

Revision ID: 5d4e7c2b1a9f
Revises: c1234567890b8
Create Date: 2026-09-15 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5d4e7c2b1a9f'
down_revision: Union[str, Sequence[str], None] = 'c1234567890b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add user_activities table."""
    # Create user_activities table
    op.create_table('user_activities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('activity_type', postgresql.ENUM(
            'button_click',
            'endpoint_visit',
            'page_view',
            'feature_interaction',
            name='activity_type'
        ), nullable=False),
        sa.Column('activity_name', sa.String(length=255), nullable=False),
        sa.Column('details', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for better query performance
    op.create_index(
        op.f('ix_user_activities_user_id'),
        'user_activities',
        ['user_id'],
        unique=False
    )
    op.create_index(
        op.f('ix_user_activities_activity_type'),
        'user_activities',
        ['activity_type'],
        unique=False
    )
    op.create_index(
        op.f('ix_user_activities_created_at'),
        'user_activities',
        ['created_at'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema - Remove user_activities table."""
    # Drop indexes
    op.drop_index(op.f('ix_user_activities_created_at'), table_name='user_activities')
    op.drop_index(op.f('ix_user_activities_activity_type'), table_name='user_activities')
    op.drop_index(op.f('ix_user_activities_user_id'), table_name='user_activities')

    # Drop table
    op.drop_table('user_activities')

    # Drop enum type
    op.execute('DROP TYPE IF EXISTS activity_type CASCADE;')
