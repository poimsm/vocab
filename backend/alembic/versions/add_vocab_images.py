"""Add vocabulary images and vocab_image_word_id field

Revision ID: add_vocab_images
Revises: add_target_fields
Create Date: 2026-10-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = 'add_vocab_images'
down_revision: Union[str, Sequence[str], None] = 'add_target_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - Add vocabulary images tables and vocab_image_word_id field."""

    # Create vocab_images table
    op.create_table(
        'vocab_images',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column('cover_image', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('main_image', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vocab_images_is_active'), 'vocab_images', ['is_active'], unique=False)
    op.create_index(op.f('ix_vocab_images_name'), 'vocab_images', ['name'], unique=False)

    # Create vocab_image_words table
    op.create_table(
        'vocab_image_words',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('vocab_image_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('word', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('definition', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column('word_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['vocab_image_id'], ['vocab_images.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vocab_image_words_category'), 'vocab_image_words', ['category'], unique=False)
    op.create_index(op.f('ix_vocab_image_words_vocab_image_id'), 'vocab_image_words', ['vocab_image_id'], unique=False)
    op.create_index(op.f('ix_vocab_image_words_word'), 'vocab_image_words', ['word'], unique=False)
    op.create_index(op.f('ix_vocab_image_words_word_order'), 'vocab_image_words', ['word_order'], unique=False)

    # Add vocab_image_word_id field to words table
    op.add_column('words', sa.Column('vocab_image_word_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
    op.create_index(op.f('ix_words_vocab_image_word_id'), 'words', ['vocab_image_word_id'], unique=False)
    op.create_foreign_key(
        'fk_words_vocab_image_word_id',
        'words',
        'vocab_image_words',
        ['vocab_image_word_id'],
        ['id']
    )


def downgrade() -> None:
    """Downgrade schema - Remove vocabulary images tables and vocab_image_word_id field."""

    # Remove foreign key and index from words table
    op.drop_constraint('fk_words_vocab_image_word_id', 'words', type_='foreignkey')
    op.drop_index(op.f('ix_words_vocab_image_word_id'), table_name='words')
    op.drop_column('words', 'vocab_image_word_id')

    # Drop vocab_image_words table
    op.drop_index(op.f('ix_vocab_image_words_word_order'), table_name='vocab_image_words')
    op.drop_index(op.f('ix_vocab_image_words_word'), table_name='vocab_image_words')
    op.drop_index(op.f('ix_vocab_image_words_vocab_image_id'), table_name='vocab_image_words')
    op.drop_index(op.f('ix_vocab_image_words_category'), table_name='vocab_image_words')
    op.drop_table('vocab_image_words')

    # Drop vocab_images table
    op.drop_index(op.f('ix_vocab_images_name'), table_name='vocab_images')
    op.drop_index(op.f('ix_vocab_images_is_active'), table_name='vocab_images')
    op.drop_table('vocab_images')
