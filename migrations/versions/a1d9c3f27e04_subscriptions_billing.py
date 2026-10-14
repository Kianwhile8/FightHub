"""subscriptions_billing

The paywall's two tables, plus the backfill that decides what every account
that already exists is entitled to.

* subscriptions — one row per user, the single source of truth for whether an
  account may write. Trial state lives here rather than on `users` so that a
  trial, a paid period and an administrator's comp cannot disagree with each
  other, and so the hottest row in the schema does not grow four more columns
  that are read on every request and consulted rarely.

  `gym_id` is reserved and unused: billing is per-user today, but adding the
  column now avoids a migration against live billing data if gym-level seats
  are built later.

* billing_events — a log of Stripe webhook deliveries. `stripe_event_id` is
  unique, and that constraint is the idempotency mechanism: Stripe delivers
  at-least-once and retries for up to three days, so without it a retried
  `invoice.paid` is applied twice.

The backfill grandfathers every existing account. Administrators and ordinary
users alike get status='comped' with a NULL comped_until, which means
indefinite access. This is deliberate and is not merely generosity: the terms
these users accepted state that the platform is free, with no paid tier and no
subscription. Dropping a paywall on them would be charging for something they
were told was free. New accounts created after this revision get the normal
trial instead, because registration builds their row itself.

Plain op.create_table rather than batch mode — these are new tables, so there
is no SQLite ALTER limitation to work around.

Revision ID: a1d9c3f27e04
Revises: c6e1f0a83b57
Create Date: 2026-10-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1d9c3f27e04'
down_revision = 'c6e1f0a83b57'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('gym_id', sa.Integer(), nullable=True),
        sa.Column('plan', sa.String(length=20), nullable=False,
                  server_default='pro'),
        sa.Column('status', sa.String(length=30), nullable=False,
                  server_default='trialing'),
        sa.Column('trial_ends_at', sa.DateTime(), nullable=True),
        sa.Column('current_period_end', sa.DateTime(), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column('stripe_customer_id', sa.String(length=64), nullable=True),
        sa.Column('stripe_subscription_id', sa.String(length=64), nullable=True),
        sa.Column('stripe_price_id', sa.String(length=64), nullable=True),
        sa.Column('comped_until', sa.DateTime(), nullable=True),
        sa.Column('comp_reason', sa.String(length=255), nullable=True),
        sa.Column('comped_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'],
                                name='fk_subscriptions_user_id',
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['gym_id'], ['gyms.id'],
                                name='fk_subscriptions_gym_id',
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['comped_by'], ['users.id'],
                                name='fk_subscriptions_comped_by',
                                ondelete='SET NULL'),
        sa.CheckConstraint("plan IN ('fighter','pro')",
                           name='ck_subscriptions_plan'),
        sa.CheckConstraint(
            "status IN ('trialing','active','past_due','canceled','incomplete',"
            "'incomplete_expired','unpaid','paused','comped','none')",
            name='ck_subscriptions_status'),
        # One subscription per account.
        sa.UniqueConstraint('user_id', name='uq_subscriptions_user_id'),
        sa.UniqueConstraint('stripe_customer_id',
                            name='uq_subscriptions_stripe_customer_id'),
        sa.UniqueConstraint('stripe_subscription_id',
                            name='uq_subscriptions_stripe_subscription_id'),
    )
    op.create_index('ix_subscriptions_user_id', 'subscriptions', ['user_id'])
    op.create_index('ix_subscriptions_stripe_customer_id', 'subscriptions',
                    ['stripe_customer_id'])
    op.create_index('ix_subscriptions_stripe_subscription_id', 'subscriptions',
                    ['stripe_subscription_id'])

    op.create_table(
        'billing_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stripe_event_id', sa.String(length=64), nullable=False),
        sa.Column('event_type', sa.String(length=80), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False,
                  server_default='received'),
        sa.Column('payload_summary', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('received','processed','ignored','failed')",
                           name='ck_billing_events_status'),
        # The idempotency key.
        sa.UniqueConstraint('stripe_event_id',
                            name='uq_billing_events_stripe_event_id'),
    )
    op.create_index('ix_billing_events_event_type', 'billing_events',
                    ['event_type'])
    op.create_index('ix_billing_events_received_at', 'billing_events',
                    ['received_at'])

    # ── backfill ───────────────────────────────────────────────────────────
    # Raw SQL rather than the ORM: a revision must keep working when the model
    # it was written against has moved on, and importing app.models here would
    # tie this file to whatever those classes look like in the future.
    #
    # Every pre-existing account is grandfathered indefinitely. Administrators
    # are recorded separately only so the reason is legible in the admin panel.
    op.execute("""
        INSERT INTO subscriptions
            (user_id, plan, status, trial_ends_at, cancel_at_period_end,
             comped_until, comp_reason, created_at, updated_at)
        SELECT
            u.id,
            CASE WHEN u.role = 'fighter' THEN 'fighter' ELSE 'pro' END,
            'comped',
            NULL,
            FALSE,
            NULL,
            CASE WHEN u.role = 'admin' THEN 'administrator'
                 ELSE 'founding account' END,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM users u
        WHERE NOT EXISTS (
            SELECT 1 FROM subscriptions s WHERE s.user_id = u.id
        )
    """)


def downgrade():
    op.drop_index('ix_billing_events_received_at', table_name='billing_events')
    op.drop_index('ix_billing_events_event_type', table_name='billing_events')
    op.drop_table('billing_events')
    op.drop_index('ix_subscriptions_stripe_subscription_id',
                  table_name='subscriptions')
    op.drop_index('ix_subscriptions_stripe_customer_id',
                  table_name='subscriptions')
    op.drop_index('ix_subscriptions_user_id', table_name='subscriptions')
    op.drop_table('subscriptions')
