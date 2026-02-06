"""add ioc audit log table

Revision ID: add_ioc_audit_log
Revises: add_wildcard_ioctype
Create Date: 2026-02-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'add_ioc_audit_log'
down_revision: Union[str, Sequence[str], None] = 'add_wildcard_ioctype'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ioc_audit_log',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ioc_id', sa.Integer(), sa.ForeignKey('iocs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('list_id', sa.Integer(), sa.ForeignKey('lists.id', ondelete='SET NULL'), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('performed_by', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_ioc_audit_log_ioc_id', 'ioc_audit_log', ['ioc_id'])


def downgrade() -> None:
    op.drop_index('ix_ioc_audit_log_ioc_id')
    op.drop_table('ioc_audit_log')
