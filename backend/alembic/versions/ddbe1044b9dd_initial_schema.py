"""initial schema

Revision ID: ddbe1044b9dd
Revises:
Create Date: 2026-01-31 12:21:24.839727

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ddbe1044b9dd'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum types first (using raw SQL for reliability)
    op.execute("DO $$ BEGIN CREATE TYPE ioctype AS ENUM ('ip', 'domain'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE exclusiontype AS ENUM ('ip', 'domain', 'cidr', 'wildcard'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE auditaction AS ENUM ('create', 'update', 'delete'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    # Create lists table
    op.create_table(
        'lists',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tags', sa.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create iocs table (use postgresql.ENUM to reference existing type)
    from sqlalchemy.dialects import postgresql
    op.create_table(
        'iocs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('value', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('type', postgresql.ENUM('ip', 'domain', name='ioctype', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create list_iocs junction table
    op.create_table(
        'list_iocs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('list_id', sa.Integer(), sa.ForeignKey('lists.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ioc_id', sa.Integer(), sa.ForeignKey('iocs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('added_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('added_by', sa.String(255), nullable=True),
        sa.UniqueConstraint('list_id', 'ioc_id', name='uq_list_ioc'),
    )

    # Create ioc_comments table
    op.create_table(
        'ioc_comments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ioc_id', sa.Integer(), sa.ForeignKey('iocs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('comment', sa.Text(), nullable=False),
        sa.Column('source', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Create ui_users table
    op.create_table(
        'ui_users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Create list_credentials table
    op.create_table(
        'list_credentials',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(255), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Create exclusions table
    op.create_table(
        'exclusions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('value', sa.String(255), unique=True, nullable=False),
        sa.Column('type', postgresql.ENUM('ip', 'domain', 'cidr', 'wildcard', name='exclusiontype', create_type=False), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Create audit_log table
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('action', postgresql.ENUM('create', 'update', 'delete', name='auditaction', create_type=False), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('entity_value', sa.String(255), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('performed_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('audit_log')
    op.drop_table('exclusions')
    op.drop_table('list_credentials')
    op.drop_table('ui_users')
    op.drop_table('ioc_comments')
    op.drop_table('list_iocs')
    op.drop_table('iocs')
    op.drop_table('lists')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS auditaction;")
    op.execute("DROP TYPE IF EXISTS exclusiontype;")
    op.execute("DROP TYPE IF EXISTS ioctype;")
