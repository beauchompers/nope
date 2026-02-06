"""add user security fields (role, lockout)

Revision ID: add_user_security_fields
Revises: add_api_keys_table
Create Date: 2026-02-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_user_security_fields'
down_revision: Union[str, Sequence[str], None] = 'add_api_keys_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add role, failed_attempts, and locked_until to ui_users."""
    # Create enum type
    role_enum = sa.Enum('admin', 'analyst', name='userrole')
    role_enum.create(op.get_bind(), checkfirst=True)

    # Add columns
    op.add_column('ui_users', sa.Column('role', role_enum, nullable=False, server_default='admin'))
    op.add_column('ui_users', sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('ui_users', sa.Column('locked_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove security fields from ui_users."""
    op.drop_column('ui_users', 'locked_until')
    op.drop_column('ui_users', 'failed_attempts')
    op.drop_column('ui_users', 'role')

    # Drop enum type
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)
