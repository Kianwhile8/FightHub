"""allow_muaythai

Adds 'muaythai' to ck_fighters_sport.

Muay Thai was already a tab in the sidebar and already in VALID_SPORTS in
app/helpers.py, so the API accepted the sport and the listing endpoints
returned an empty set for it quite happily. Only the write failed: the CHECK
constraint from the initial schema allowed three disciplines, so creating a
Muay Thai fighter died with a raw IntegrityError surfaced to the user as a SQL
string. This makes the database agree with the rest of the application.

Revision ID: d8f3b17c95a2
Revises: c2a91f6d4e18
Create Date: 2026-09-18 00:00:00.000000

"""
from alembic import op


revision = 'd8f3b17c95a2'
down_revision = 'c2a91f6d4e18'
branch_labels = None
depends_on = None

OLD = "sport IN ('kickboxing','mma','boxing')"
NEW = "sport IN ('kickboxing','mma','boxing','muaythai')"


def upgrade():
    # batch_alter_table recreates the table on SQLite, which is the only way to
    # change a CHECK there; on Postgres it drops and re-adds the constraint.
    with op.batch_alter_table('fighters', schema=None) as batch_op:
        batch_op.drop_constraint('ck_fighters_sport', type_='check')
        batch_op.create_check_constraint('ck_fighters_sport', NEW)


def downgrade():
    # Any Muay Thai fighters must be gone before the narrower constraint can be
    # reapplied, or this fails — which is the correct outcome rather than
    # silently discarding them.
    with op.batch_alter_table('fighters', schema=None) as batch_op:
        batch_op.drop_constraint('ck_fighters_sport', type_='check')
        batch_op.create_check_constraint('ck_fighters_sport', OLD)
