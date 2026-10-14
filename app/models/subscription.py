from datetime import datetime
from ..extensions import db

# The two billing plans. 'pro' covers coaches and promoters at the higher
# price; 'fighter' is the individual competitor tier. Deliberately named after
# the plan rather than the role, because two roles share one plan and a column
# called `role` would imply otherwise.
VALID_PLANS = ("fighter", "pro")

# Every state a subscription row can be in. The first eight mirror Stripe's own
# subscription statuses so a webhook can be applied without translation; the
# last two are ours.
#
#   comped — access granted by an administrator, with no Stripe subscription
#            behind it. Used for founding accounts, comps and bank transfers.
#   none   — the trial has been used up and nothing was ever paid. Distinct
#            from 'canceled', which means there WAS a subscription.
VALID_STATUSES = (
    "trialing", "active", "past_due", "canceled", "incomplete",
    "incomplete_expired", "unpaid", "paused", "comped", "none",
)


class Subscription(db.Model):
    """One row per user: the single source of truth for whether they may write.

    Trial state lives here rather than on `users` for three reasons.

    First, every piece of entitlement state sits in one row, so a trial, a paid
    period and an administrator's comp cannot disagree with each other — there
    is one place to read and one place to write.

    Second, `users` is already the hottest row in the schema. `current_user()`
    loads it on every single request, and it is already carrying terms, privacy,
    verification and gender columns. Four more date columns on it would be read
    constantly and consulted rarely.

    Third, deleting the row is a clean reset. During testing that matters more
    than it sounds: resetting a trial is `DELETE FROM subscriptions WHERE ...`
    rather than remembering which of five columns on `users` to put back.

    Nothing here is read directly for gating. `BillingService.entitlement()`
    computes the answer, and `has_active_access()` in app/helpers.py is the one
    function that decides. In particular `stripe_price_id` is recorded for
    audit and never consulted — the price a user should pay is derived from
    their role server-side, every time.
    """

    __tablename__ = "subscriptions"
    __table_args__ = (
        db.CheckConstraint(
            "plan IN ('fighter','pro')",
            name="ck_subscriptions_plan",
        ),
        db.CheckConstraint(
            "status IN ('trialing','active','past_due','canceled','incomplete',"
            "'incomplete_expired','unpaid','paused','comped','none')",
            name="ck_subscriptions_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # Unique: one subscription per account. CASCADE because an entitlement for a
    # deleted user is meaningless — but note that AuthService.delete_user must
    # cancel the Stripe subscription BEFORE the delete, or Stripe keeps billing
    # somebody whose row has gone.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    # Reserved, and unused in v1. Billing is per-user today: a gym with three
    # coaches needs three subscriptions, because a Gym has exactly one coach_id
    # and there is no gym-membership table to count seats against.
    #
    # The column exists now because adding it later would mean a migration on a
    # table with live billing data, whereas making gym-level seats work from
    # here is a change to one function — `has_active_access` grows an "or the
    # gym this coach belongs to has an active plan" branch. Keep it nullable
    # and keep nothing reading it until that feature is actually built.
    gym_id = db.Column(
        db.Integer,
        db.ForeignKey("gyms.id", ondelete="SET NULL"),
        nullable=True,
    )
    plan   = db.Column(db.String(20), nullable=False, default="pro")
    status = db.Column(db.String(30), nullable=False, default="trialing")

    # The trial is run here, not in Stripe: it starts at registration, before
    # the user has a Stripe customer at all, and takes no card.
    trial_ends_at        = db.Column(db.DateTime, nullable=True)
    current_period_end   = db.Column(db.DateTime, nullable=True)
    cancel_at_period_end = db.Column(db.Boolean, nullable=False, default=False)

    stripe_customer_id     = db.Column(db.String(64), nullable=True, unique=True, index=True)
    stripe_subscription_id = db.Column(db.String(64), nullable=True, unique=True, index=True)
    # Audit only. Never read to decide what someone should be charged.
    stripe_price_id        = db.Column(db.String(64), nullable=True)

    # Administrator grant. NULL `comped_until` with status 'comped' means
    # indefinite, which is what founding accounts get.
    comped_until = db.Column(db.DateTime, nullable=True)
    comp_reason  = db.Column(db.String(255), nullable=True)
    comped_by    = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    # Explicit foreign_keys: there are two FKs to users.id on this table
    # (user_id and comped_by), so SQLAlchemy cannot infer the join.
    user       = db.relationship("User", foreign_keys=[user_id])
    comped_by_user = db.relationship("User", foreign_keys=[comped_by])

    def to_dict(self) -> dict:
        """Full row, for administrators and the CLI. Includes Stripe ids."""
        return {
            "id":                     self.id,
            "user_id":                self.user_id,
            "gym_id":                 self.gym_id,
            "plan":                   self.plan,
            "status":                 self.status,
            "trial_ends_at":          _iso(self.trial_ends_at),
            "current_period_end":     _iso(self.current_period_end),
            "cancel_at_period_end":   bool(self.cancel_at_period_end),
            "stripe_customer_id":     self.stripe_customer_id,
            "stripe_subscription_id": self.stripe_subscription_id,
            "stripe_price_id":        self.stripe_price_id,
            "comped_until":           _iso(self.comped_until),
            "comp_reason":            self.comp_reason,
            "comped_by":              self.comped_by,
            "created_at":             _iso(self.created_at),
            "updated_at":             _iso(self.updated_at),
        }

    def to_public_dict(self) -> dict:
        """What may reach the browser.

        The Stripe ids are left out on purpose. They are account identifiers at
        a payment processor, the client has no use for them — every Stripe call
        is made server-side — and the one thing the page needs to know about
        them is whether a subscription exists at all, which is what
        `manageable` on the entitlement envelope answers.
        """
        return {
            "plan":                 self.plan,
            "status":               self.status,
            "trial_ends_at":        _iso(self.trial_ends_at),
            "current_period_end":   _iso(self.current_period_end),
            "cancel_at_period_end": bool(self.cancel_at_period_end),
            "comped_until":         _iso(self.comped_until),
        }


class WebhookEvent(db.Model):
    """A log of Stripe webhook deliveries, for idempotency and for debugging.

    Stripe delivers at-least-once and retries a failing endpoint for up to
    three days with backoff. Without a record of what has already been applied,
    a retried `invoice.paid` is processed twice.

    `stripe_event_id` being unique is the whole mechanism: the handler inserts
    the row first and commits, then processes, then marks it processed. A
    duplicate insert fails, and the handler can tell "already done" from "began
    and crashed" by the existing row's status.

    Only a summary of the payload is stored, never the raw event. Raw Stripe
    events carry the customer's email and billing address, so keeping them
    would put a new category of personal data into a new table — and drag a
    retention entry into the privacy notice — for no operational gain.
    """

    __tablename__ = "billing_events"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('received','processed','ignored','failed')",
            name="ck_billing_events_status",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # The idempotency key. Unique is load-bearing, not a nicety.
    stripe_event_id = db.Column(db.String(64), nullable=False, unique=True)
    event_type      = db.Column(db.String(80), nullable=False, index=True)
    status          = db.Column(db.String(20), nullable=False, default="received")
    # A trimmed summary: ids, type, created, status. Not the event body.
    payload_summary = db.Column(db.Text, nullable=True)
    received_at     = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    processed_at    = db.Column(db.DateTime, nullable=True)
    error           = db.Column(db.Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "stripe_event_id": self.stripe_event_id,
            "event_type":      self.event_type,
            "status":          self.status,
            "payload_summary": self.payload_summary,
            "received_at":     _iso(self.received_at),
            "processed_at":    _iso(self.processed_at),
            "error":           self.error,
        }


def _iso(value):
    return value.isoformat() if value else None
