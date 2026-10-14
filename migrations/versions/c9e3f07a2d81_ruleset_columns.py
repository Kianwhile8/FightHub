"""ruleset_columns

Revision ID: c9e3f07a2d81
Revises: 4d55fb60a84e
Create Date: 2026-07-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c9e3f07a2d81'
down_revision = '4d55fb60a84e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('fight_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ruleset', sa.String(50), nullable=True))

    with op.batch_alter_table('event_bouts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ruleset', sa.String(50), nullable=True))


def downgrade():
    with op.batch_alter_table('fight_history', schema=None) as batch_op:
        batch_op.drop_column('ruleset')

    with op.batch_alter_table('event_bouts', schema=None) as batch_op:
        batch_op.drop_column('ruleset')
