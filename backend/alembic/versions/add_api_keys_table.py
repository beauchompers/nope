"""add api_keys table

Revision ID: add_api_keys_table
Revises: add_list_type
Create Date: 2026-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_api_keys_table'
down_revision: Union[str, Sequence[str], None] = 'add_list_type'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create api_keys table for MCP API key authentication."""
    op.create_table(
        'api_keys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('key', sa.String(255), nullable=False),  # Encrypted with Fernet
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Drop api_keys table."""
    op.drop_table('api_keys')
