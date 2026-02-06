"""add hash ioc types (md5, sha1, sha256)

Revision ID: add_hash_ioc_types
Revises: add_ioc_audit_log
Create Date: 2026-02-01

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_hash_ioc_types'
down_revision: Union[str, Sequence[str], None] = 'add_ioc_audit_log'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'md5', 'sha1', and 'sha256' values to ioctype enum."""
    # PostgreSQL allows adding values to enums
    # Use IF NOT EXISTS to make it idempotent
    op.execute("ALTER TYPE ioctype ADD VALUE IF NOT EXISTS 'md5';")
    op.execute("ALTER TYPE ioctype ADD VALUE IF NOT EXISTS 'sha1';")
    op.execute("ALTER TYPE ioctype ADD VALUE IF NOT EXISTS 'sha256';")


def downgrade() -> None:
    """Remove hash types from ioctype enum.

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the type and updating all references.
    For simplicity, we leave the enum values in place on downgrade.
    """
    pass
