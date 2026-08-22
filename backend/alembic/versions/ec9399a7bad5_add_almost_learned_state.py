"""add_almost_learned_state

Revision ID: ec9399a7bad5
Revises: 25d27f40ee18
Create Date: 2026-08-22 06:05:27.137761

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'ec9399a7bad5'
down_revision: Union[str, Sequence[str], None] = '25d27f40ee18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Strategy: Create new enum type with all values, migrate column, drop old type

    # 1. Create the new enum with all values including almost_learned
    # Note: Values are in UPPERCASE to match existing enum values
    op.execute("""
        CREATE TYPE learningstate_new AS ENUM (
            'NEW', 'LEARNING', 'REINFORCING', 'SPACING',
            'ALMOST_LEARNED', 'LEARNED', 'REVIEW'
        )
    """)

    # 2. Migrate the column to the new type
    op.execute("""
        ALTER TABLE word_statistics
        ALTER COLUMN learning_state TYPE learningstate_new
        USING learning_state::text::learningstate_new
    """)

    # 3. Drop the old enum
    op.execute("DROP TYPE learningstate")

    # 4. Rename the new enum to the original name
    op.execute("ALTER TYPE learningstate_new RENAME TO learningstate")


def downgrade() -> None:
    """Downgrade schema."""
    # Create the old enum without almost_learned
    op.execute("""
        CREATE TYPE learningstate_old AS ENUM (
            'NEW', 'LEARNING', 'REINFORCING', 'SPACING', 'LEARNED', 'REVIEW'
        )
    """)

    # Migrate back
    op.execute("""
        ALTER TABLE word_statistics
        ALTER COLUMN learning_state TYPE learningstate_old
        USING learning_state::text::learningstate_old
    """)

    # Drop the new enum
    op.execute("DROP TYPE learningstate")

    # Rename back
    op.execute("ALTER TYPE learningstate_old RENAME TO learningstate")
