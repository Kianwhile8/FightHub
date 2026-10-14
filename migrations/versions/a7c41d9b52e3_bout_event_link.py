"""bout_event_link

Links a logged fight back to the event it took place at, and lets a bout on an
event card be checked off as complete.

Revision ID: a7c41d9b52e3
Revises: c9e3f07a2d81
Create Date: 2026-08-13 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a7c41d9b52e3'
down_revision = 'c9e3f07a2d81'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('fight_history', schema=None) as batch_op:
        batch_op.add_column(sa.Column('event_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_fight_history_event_id', ['event_id'])
        batch_op.create_foreign_key(
            'fk_fight_history_event_id', 'events', ['event_id'], ['id'],
            ondelete='SET NULL',
        )

    with op.batch_alter_table('event_bouts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('completed', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))
        batch_op.add_column(sa.Column('result', sa.String(1), nullable=True))
        batch_op.add_column(sa.Column('method', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('fight_date', sa.String(20), nullable=True))


def downgrade():
    with op.batch_alter_table('event_bouts', schema=None) as batch_op:
        batch_op.drop_column('fight_date')
        batch_op.drop_column('method')
        batch_op.drop_column('result')
        batch_op.drop_column('completed')

    with op.batch_alter_table('fight_history', schema=None) as batch_op:
        batch_op.drop_constraint('fk_fight_history_event_id', type_='foreignkey')
        batch_op.drop_index('ix_fight_history_event_id')
        batch_op.drop_column('event_id')
