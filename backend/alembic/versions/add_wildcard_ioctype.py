"""add wildcard to ioctype enum

Revision ID: add_wildcard_ioctype
Revises: ddbe1044b9dd
Create Date: 2026-01-31 19:20:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_wildcard_ioctype'
down_revision: Union[str, Sequence[str], None] = 'ddbe1044b9dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'wildcard' value to ioctype enum."""
    # PostgreSQL allows adding values to enums
    # Use IF NOT EXISTS to make it idempotent
    op.execute("ALTER TYPE ioctype ADD VALUE IF NOT EXISTS 'wildcard';")


def downgrade() -> None:
    """Remove 'wildcard' from ioctype enum.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the type and updating all references.
    For simplicity, we leave the enum value in place on downgrade.
    """
    pass
