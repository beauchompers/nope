"""add list_type column to lists table

Revision ID: add_list_type
Revises: add_hash_ioc_types
Create Date: 2026-02-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_list_type'
down_revision: Union[str, Sequence[str], None] = 'add_hash_ioc_types'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add list_type column to lists table.

    Adds a VARCHAR(10) column with default 'mixed' and NOT NULL constraint.
    Existing lists will automatically get 'mixed' as their list_type.
    Valid values: 'ip', 'domain', 'hash', 'mixed'
    """
    op.add_column(
        'lists',
        sa.Column('list_type', sa.String(10), nullable=False, server_default='mixed')
    )


def downgrade() -> None:
    """Remove list_type column from lists table."""
    op.drop_column('lists', 'list_type')
