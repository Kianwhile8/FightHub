"""email_verification

Adds the verified-address flag ahead of the confirmation-email flow. Nothing
gates on it yet — REQUIRE_VERIFIED_EMAIL turns enforcement on once mail is
sending.

Existing accounts are grandfathered in as verified. They were created before
there was any way to confirm an address, so leaving them false would lock every
current user out the moment enforcement is switched on.

Revision ID: e7b21c904f6a
Revises: d3f8a1c47b09
Create Date: 2026-08-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e7b21c904f6a'
down_revision = 'd3f8a1c47b09'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified', sa.Boolean(),
                                      nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('email_verified_at', sa.DateTime(),
                                      nullable=True))

    op.execute("UPDATE users SET email_verified = TRUE")


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('email_verified_at')
        batch_op.drop_column('email_verified')
