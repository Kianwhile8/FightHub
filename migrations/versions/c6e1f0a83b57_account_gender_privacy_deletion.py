"""account_gender_privacy_deletion

Three related additions, in one revision because they land together:

* users.gender — the answer given at registration. Asked only of fighters, so
  every coach, promoter and pre-existing account stays NULL. Unlike
  fighters.gender this permits 'undisclosed', which records a stated refusal to
  answer as distinct from never having been asked. Matchmaking reads
  fighters.gender, not this column, so 'undisclosed' never reaches the pairing
  rules — it simply leaves the fighter profile's own value unset.

* users.privacy_version / privacy_accepted_at — which version of the privacy
  notice an account was shown, and when. The terms and the notice are now two
  separate documents that can be reissued independently, so one pair of columns
  can no longer speak for both.

* deletion_requests — the erasure queue. Both foreign keys are ON DELETE SET
  NULL rather than CASCADE: the row is the audit trail for a deletion, so it
  has to outlive the account it refers to.

Revision ID: c6e1f0a83b57
Revises: b93c05af71de
Create Date: 2026-09-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c6e1f0a83b57'
down_revision = 'b93c05af71de'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gender', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('privacy_version', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('privacy_accepted_at', sa.DateTime(), nullable=True))
        batch_op.create_check_constraint(
            'ck_users_gender',
            "gender IS NULL OR gender IN ('male','female','undisclosed')")

    op.create_table(
        'deletion_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('user_email', sa.String(length=255), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False,
                  server_default='pending'),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
                                name='fk_deletion_requests_user_id',
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'],
                                name='fk_deletion_requests_resolved_by',
                                ondelete='SET NULL'),
        sa.CheckConstraint("status IN ('pending','completed','rejected','cancelled')",
                           name='ck_deletion_requests_status'),
    )
    with op.batch_alter_table('deletion_requests', schema=None) as batch_op:
        batch_op.create_index('ix_deletion_requests_user_id', ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('deletion_requests', schema=None) as batch_op:
        batch_op.drop_index('ix_deletion_requests_user_id')
    op.drop_table('deletion_requests')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('ck_users_gender', type_='check')
        batch_op.drop_column('privacy_accepted_at')
        batch_op.drop_column('privacy_version')
        batch_op.drop_column('gender')
