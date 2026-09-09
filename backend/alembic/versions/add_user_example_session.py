"""Add UserExampleSession model

Revision ID: c1234567890b5
Revises: c1234567890b4
Create Date: 2026-09-08 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision = 'c1234567890b5_base'
down_revision = 'c1234567890b4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_example_sessions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('buffer_queue_item_ids', sa.String(), nullable=False),
        sa.Column('buffer_position', sa.Integer(), nullable=False),
        sa.Column('resolved_queue_item_ids', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index(op.f('ix_user_example_sessions_created_at'), 'user_example_sessions', ['created_at'], unique=False)
    op.create_index(op.f('ix_user_example_sessions_user_id'), 'user_example_sessions', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_user_example_sessions_user_id'), table_name='user_example_sessions')
    op.drop_index(op.f('ix_user_example_sessions_created_at'), table_name='user_example_sessions')
    op.drop_table('user_example_sessions')
