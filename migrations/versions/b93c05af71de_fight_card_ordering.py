"""fight_card_ordering

Adds the pieces the fight-card builder needs:

* events.max_bouts  — the size the card is being built to (5-20). The arrange
  phase opens once the card holds this many bouts.
* events.created_by — who set the event up. Events predating this column have
  no owner recorded, so they keep the old behaviour of being editable by any
  promoter; only events created from now on are restricted to their creator.
* event_bouts.order_index — position on the card. 0 is the main event, which
  tops the running order and is fought last. NULL means the card has not been
  arranged, and those bouts fall back to creation order.

Revision ID: b93c05af71de
Revises: f4b8d2e6071c
Create Date: 2026-09-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b93c05af71de'
down_revision = 'f4b8d2e6071c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('max_bouts', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_events_created_by', 'users',
                                    ['created_by'], ['id'], ondelete='SET NULL')

    with op.batch_alter_table('event_bouts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('order_index', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('event_bouts', schema=None) as batch_op:
        batch_op.drop_column('order_index')

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_constraint('fk_events_created_by', type_='foreignkey')
        batch_op.drop_column('created_by')
        batch_op.drop_column('max_bouts')
