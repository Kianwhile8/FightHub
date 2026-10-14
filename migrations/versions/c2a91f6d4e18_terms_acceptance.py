"""terms_acceptance

Records which version of the terms and privacy notice each account agreed to,
and when. UK GDPR Art. 7(1) puts the burden of proof on the controller, so the
agreement has to be stored as data rather than inferred from the account
existing at all.

Both columns are nullable and existing accounts are deliberately left NULL.
Backfilling them with the current version would be manufacturing a consent
record for people who were never shown the document — the opposite of what
Art. 7(1) is asking for. A NULL means "has not agreed to the current version",
which is what prompts those users to read and accept it on their next sign-in.

Revision ID: c2a91f6d4e18
Revises: e7b21c904f6a
Create Date: 2026-09-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c2a91f6d4e18'
down_revision = 'e7b21c904f6a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('terms_version', sa.String(length=20),
                                      nullable=True))
        batch_op.add_column(sa.Column('terms_accepted_at', sa.DateTime(),
                                      nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('terms_accepted_at')
        batch_op.drop_column('terms_version')
