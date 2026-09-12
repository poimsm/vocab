"""Add path health monitoring and repair tables

Revision ID: c1234567890b7
Revises: ['c1234567890b6', 'c1234567890b5_base']
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1234567890b7'
down_revision: Union[str, Sequence[str], None] = ['c1234567890b6', 'c1234567890b5_base']
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create learning_path_anomalies table
    op.create_table(
        'learning_path_anomalies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('anomaly_type', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('details', sa.String(), nullable=False, server_default='{}'),
        sa.Column('auto_repair_attempted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('auto_repair_successful', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('repair_description', sa.String(), nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_learning_path_anomalies_user_id'), 'learning_path_anomalies', ['user_id'], unique=False)
    op.create_index(op.f('ix_learning_path_anomalies_type'), 'learning_path_anomalies', ['type'], unique=False)
    op.create_index(op.f('ix_learning_path_anomalies_anomaly_type'), 'learning_path_anomalies', ['anomaly_type'], unique=False)
    op.create_index(op.f('ix_learning_path_anomalies_auto_repair_attempted'), 'learning_path_anomalies', ['auto_repair_attempted'], unique=False)
    op.create_index(op.f('ix_learning_path_anomalies_auto_repair_successful'), 'learning_path_anomalies', ['auto_repair_successful'], unique=False)
    op.create_index(op.f('ix_learning_path_anomalies_is_resolved'), 'learning_path_anomalies', ['is_resolved'], unique=False)
    op.create_index(op.f('ix_learning_path_anomalies_created_at'), 'learning_path_anomalies', ['created_at'], unique=False)

    # Create path_repair_logs table
    op.create_table(
        'path_repair_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('repair_type', sa.String(length=100), nullable=False),
        sa.Column('before_state', sa.String(), nullable=False),
        sa.Column('after_state', sa.String(), nullable=False),
        sa.Column('items_affected', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('triggered_by', sa.String(length=100), nullable=False, server_default='auto_repair'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_path_repair_logs_user_id'), 'path_repair_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_path_repair_logs_type'), 'path_repair_logs', ['type'], unique=False)
    op.create_index(op.f('ix_path_repair_logs_success'), 'path_repair_logs', ['success'], unique=False)
    op.create_index(op.f('ix_path_repair_logs_created_at'), 'path_repair_logs', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_path_repair_logs_created_at'), table_name='path_repair_logs')
    op.drop_index(op.f('ix_path_repair_logs_success'), table_name='path_repair_logs')
    op.drop_index(op.f('ix_path_repair_logs_type'), table_name='path_repair_logs')
    op.drop_index(op.f('ix_path_repair_logs_user_id'), table_name='path_repair_logs')
    op.drop_table('path_repair_logs')

    op.drop_index(op.f('ix_learning_path_anomalies_created_at'), table_name='learning_path_anomalies')
    op.drop_index(op.f('ix_learning_path_anomalies_is_resolved'), table_name='learning_path_anomalies')
    op.drop_index(op.f('ix_learning_path_anomalies_auto_repair_successful'), table_name='learning_path_anomalies')
    op.drop_index(op.f('ix_learning_path_anomalies_auto_repair_attempted'), table_name='learning_path_anomalies')
    op.drop_index(op.f('ix_learning_path_anomalies_anomaly_type'), table_name='learning_path_anomalies')
    op.drop_index(op.f('ix_learning_path_anomalies_type'), table_name='learning_path_anomalies')
    op.drop_index(op.f('ix_learning_path_anomalies_user_id'), table_name='learning_path_anomalies')
    op.drop_table('learning_path_anomalies')
