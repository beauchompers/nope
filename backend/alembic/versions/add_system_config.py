"""add system_config table

Revision ID: add_system_config
Revises: add_user_security_fields
Create Date: 2026-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_system_config'
down_revision: Union[str, Sequence[str], None] = 'add_user_security_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create system_config table for key-value settings storage."""
    op.create_table(
        'system_config',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('key', sa.String(255), unique=True, nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
    )


def downgrade() -> None:
    """Drop system_config table."""
    op.drop_table('system_config')
