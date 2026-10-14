"""fighter_gender

Adds Fighter.gender, which gates matchmaking and bout creation: combat sports
are contested in single-sex divisions, so a mixed pairing is not a preference
to be scored down but a matchup that must not be offered at all.

Nullable, and existing rows are deliberately left NULL. Guessing a fighter's
sex from their name would be both unreliable and offensive, and defaulting
everyone to one value would produce exactly the mixed pairings this is meant
to prevent. NULL means "not stated", and the rule applies where it can: a
pairing is refused when both sides are known and differ.

Revision ID: f4b8d2e6071c
Revises: e5c704a18b63
Create Date: 2026-09-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f4b8d2e6071c'
down_revision = 'e5c704a18b63'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('fighters', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gender', sa.String(length=10), nullable=True))
        batch_op.create_check_constraint(
            'ck_fighters_gender', "gender IS NULL OR gender IN ('male','female')")


def downgrade():
    with op.batch_alter_table('fighters', schema=None) as batch_op:
        batch_op.drop_constraint('ck_fighters_gender', type_='check')
        batch_op.drop_column('gender')
