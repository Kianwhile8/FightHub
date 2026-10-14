"""demo_records

Manifest of rows created by `flask seed-demo`, so `flask clear-demo` can remove
exactly those and leave real data alone. See app/models/demo.py for why this
cannot be a flag or a date filter.

Revision ID: e5c704a18b63
Revises: d8f3b17c95a2
Create Date: 2026-09-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5c704a18b63'
down_revision = 'd8f3b17c95a2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'demo_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.String(length=32), nullable=False),
        sa.Column('entity', sa.String(length=30), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_demo_records_run_id', 'demo_records', ['run_id'])


def downgrade():
    op.drop_index('ix_demo_records_run_id', table_name='demo_records')
    op.drop_table('demo_records')
