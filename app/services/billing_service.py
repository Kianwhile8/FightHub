"""BillingService — entitlement state and, from phase 4, Stripe.

Blueprints reach this through `current_app.billing_db`, the same way they reach
AuthService through `current_app.auth_db`.

The important function here is `entitlement()`. It is the only place that
decides whether an account may write, and it returns one envelope shape that
`/api/auth/me`, `/api/billing/status`, the 402 body and the admin user list all
serve — so those four can never disagree about a user's state.
"""

import math
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.subscription import Subscription, VALID_PLANS, VALID_STATUSES

# Pinned deliberately. The webhook handlers read named fields off Stripe objects,
# and the account's default API version can be changed from the dashboard — which
# would otherwise reshape those payloads with no deploy and no warning.
STRIPE_API_VERSION = "2024-06-20"

# Which plan each role buys. Two roles share the 'pro' plan.
_ROLE_PLAN = {
    "fighter":  "fighter",
    "coach":    "pro",
    "promoter": "pro",
}

# Statuses that mean a paid subscription is running. 'past_due' is included
# deliberately — see _is_active.
_PAID_STATUSES = ("active", "past_due")


class BillingService:

    # ── rows ───────────────────────────────────────────────────────────────

    def ensure_for_user(self, user_id: int, role: str,
                        created_at: datetime = None) -> Subscription:
        """Return this user's subscription row, creating a trialing one if absent.

        `created_at` is the account's creation time, and the trial is measured
        from it rather than from now. That matters for self-healing: if a row is
        created late for an account that has existed for a year — a user who
        slipped through the migration backfill, say — they get a trial that
        expired eleven months ago, not a fresh one. Handing out a new trial
        every time a row goes missing would make the trial renewable by anyone
        who noticed.
        """
        existing = Subscription.query.filter_by(user_id=user_id).first()
        if existing:
            return existing

        trial_days = current_app.config.get("TRIAL_DAYS", 7)
        base = created_at or datetime.utcnow()
        sub = Subscription(
            user_id=user_id,
            plan=self.plan_for_role(role),
            status="trialing",
            trial_ends_at=base + timedelta(days=trial_days),
        )
        db.session.add(sub)
        try:
            db.session.commit()
        except IntegrityError:
            # Two concurrent requests both found no row. The unique constraint on
            # user_id settles it; the loser re-reads the winner's row.
            db.session.rollback()
            return Subscription.query.filter_by(user_id=user_id).first()
        return sub

    def build_for_new_user(self, user_id: int, role: str,
                           created_at: datetime = None,
                           status: str = "trialing",
                           comp_reason: str = None) -> Subscription:
        """Construct a row for a brand-new account WITHOUT committing.

        AuthService.register adds this to the same transaction as the User, so a
        user can never exist without an entitlement row — and a failed
        registration rolls both back together.
        """
        trial_days = current_app.config.get("TRIAL_DAYS", 7)
        base = created_at or datetime.utcnow()
        return Subscription(
            user_id=user_id,
            plan=self.plan_for_role(role),
            status=status,
            # A comped account has no trial to run down.
            trial_ends_at=None if status == "comped" else base + timedelta(days=trial_days),
            comp_reason=comp_reason,
            created_at=base,
            updated_at=base,
        )

    def get_for_user(self, user_id: int, role: str = None,
                     created_at: datetime = None) -> Subscription | None:
        """This user's row, self-healing if `role` is given."""
        sub = Subscription.query.filter_by(user_id=user_id).first()
        if sub is None and role:
            sub = self.ensure_for_user(user_id, role, created_at)
        return sub

    # ── pricing ────────────────────────────────────────────────────────────

    def plan_for_role(self, role: str) -> str:
        """Which plan this role is on. Defaults to the higher tier."""
        return _ROLE_PLAN.get(role, "pro")

    def price_for_role(self, role: str) -> tuple[str, str]:
        """(stripe_price_id, plan) for a role.

        Server-side only, and the reason /api/billing/checkout ignores its
        request body entirely. A client that could name its own price id could
        name the £10 one while registering as a coach.
        """
        if role == "admin":
            raise ValueError("Administrator accounts do not require a subscription.")
        plan = self.plan_for_role(role)
        key = "STRIPE_PRICE_FIGHTER" if plan == "fighter" else "STRIPE_PRICE_PRO"
        price_id = current_app.config.get(key)
        if not price_id:
            raise ValueError(f"{key} is not configured. See .env.example.")
        return price_id, plan

    def price_display(self, plan: str) -> dict:
        """What the UI prints for a plan. Display only, never authoritative."""
        pence = (current_app.config.get("PRICE_FIGHTER_PENCE", 1000)
                 if plan == "fighter"
                 else current_app.config.get("PRICE_PRO_PENCE", 2000))
        return {
            "amount_pence": pence,
            "currency":     current_app.config.get("BILLING_CURRENCY", "gbp"),
            "interval":     "year",
        }

    # ── entitlement ────────────────────────────────────────────────────────

    def entitlement(self, user: dict | None) -> dict:
        """The canonical entitlement envelope for a user.

        Shape is fixed, because four callers serve it and a fifth reads it:
        /api/auth/me, /api/billing/status, the 402 body, the admin list, and
        useEntitlement() in the frontend.

        `state` is one of:
            admin     — never pays
            comped    — granted by an administrator (includes founding accounts)
            trialing  — inside the free trial
            active    — paying
            past_due  — a renewal failed but Stripe is still retrying
            expired   — had access, no longer does
            none      — never had anything
        """
        if not user:
            return self._envelope(active=False, state="none", plan=None)

        role = user.get("role")
        if role == "admin":
            return self._envelope(active=True, state="admin",
                                  plan=self.plan_for_role(role))

        # Billing disabled: everybody is entitled, and the envelope says why so
        # the UI does not show a trial banner counting down to nothing.
        if not current_app.config.get("BILLING_ENABLED"):
            return self._envelope(active=True, state="comped",
                                  plan=self.plan_for_role(role))

        created = user.get("created_at")
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created)
            except ValueError:
                created = None
        sub = self.get_for_user(user["id"], role, created)
        if sub is None:
            return self._envelope(active=False, state="none",
                                  plan=self.plan_for_role(role))

        now = datetime.utcnow()
        state = self._state(sub, now)
        return self._envelope(
            active=self._is_active(sub, now),
            state=state,
            plan=sub.plan,
            trial_ends_at=sub.trial_ends_at,
            trial_days_left=self._days_left(sub.trial_ends_at, now)
                            if state == "trialing" else None,
            current_period_end=sub.current_period_end,
            cancel_at_period_end=bool(sub.cancel_at_period_end),
            # Only worth offering the Stripe portal link if there is something
            # there to manage.
            manageable=bool(sub.stripe_subscription_id),
            comped_until=sub.comped_until,
            comp_reason=sub.comp_reason,
        )

    def _is_active(self, sub: Subscription, now: datetime) -> bool:
        """Whether this row entitles its user to write. The one truth."""
        if sub.status == "comped":
            # NULL comped_until means indefinite — what founding accounts get.
            return sub.comped_until is None or sub.comped_until > now
        if sub.status == "trialing":
            return sub.trial_ends_at is not None and sub.trial_ends_at > now
        if sub.status in _PAID_STATUSES:
            # 'past_due' keeps access on purpose. Stripe's smart retries run for
            # about three weeks, and cutting a promoter off the week of their
            # event because a card expired is the worst possible moment to do
            # it — they are almost certainly going to pay. Access ends at
            # 'canceled' or 'unpaid', which is Stripe giving up.
            if sub.current_period_end is None:
                return True
            grace = timedelta(days=current_app.config.get("BILLING_GRACE_DAYS", 2))
            return sub.current_period_end + grace > now
        return False

    def _state(self, sub: Subscription, now: datetime) -> str:
        if sub.status == "comped":
            return "comped" if self._is_active(sub, now) else "expired"
        if sub.status == "trialing":
            return "trialing" if self._is_active(sub, now) else "expired"
        if sub.status == "past_due":
            return "past_due"
        if sub.status == "active":
            return "active" if self._is_active(sub, now) else "expired"
        if sub.status == "none":
            return "none"
        # canceled, unpaid, incomplete, incomplete_expired, paused — all of
        # these had a subscription that is no longer paying.
        return "expired"

    @staticmethod
    def _days_left(when: datetime | None, now: datetime) -> int | None:
        if when is None:
            return None
        seconds = (when - now).total_seconds()
        if seconds <= 0:
            return 0
        # Rounded up, so eighteen hours remaining reads as "1 day left" rather
        # than "0 days left", which would look like it had already expired.
        return math.ceil(seconds / 86400)

    def _envelope(self, *, active: bool, state: str, plan: str | None,
                  trial_ends_at: datetime = None, trial_days_left: int = None,
                  current_period_end: datetime = None,
                  cancel_at_period_end: bool = False,
                  manageable: bool = False,
                  comped_until: datetime = None,
                  comp_reason: str = None) -> dict:
        """One fixed shape, built in one place.

        Four callers serve this — /api/auth/me, /api/billing/status, the 402 body
        and the admin user list — and the frontend's useEntitlement() reads it.
        Building it here rather than at each call site is what stops those four
        disagreeing about an account's state.

        No Stripe ids: they are identifiers at a payment processor, the client
        makes no Stripe calls, and `manageable` already answers the only
        question the page has about them.

        `comp_reason` is an administrator's own note ("founding account"), shown
        in the admin list and on the user's billing page. It is deliberately
        plain enough to show the account holder.
        """
        return {
            "active":               bool(active),
            "state":                state,
            "plan":                 plan,
            "trial_ends_at":        trial_ends_at.isoformat() if trial_ends_at else None,
            "trial_days_left":      trial_days_left,
            "current_period_end":   current_period_end.isoformat() if current_period_end else None,
            "cancel_at_period_end": bool(cancel_at_period_end),
            "manageable":           bool(manageable),
            "comped_until":         comped_until.isoformat() if comped_until else None,
            "comp_reason":          comp_reason,
            "price":               self.price_display(plan) if plan else None,
        }

    # ── administrator grants ───────────────────────────────────────────────

    def grant_comp(self, user_id: int, admin_id: int, days: int | None,
                   reason: str = None) -> dict:
        """Give an account access without a Stripe subscription.

        `days=None` means indefinitely, which is what founding accounts and
        permanent comps get.
        """
        sub = Subscription.query.filter_by(user_id=user_id).first()
        if sub is None:
            raise ValueError("That account has no subscription record.")
        sub.status = "comped"
        sub.comped_until = (datetime.utcnow() + timedelta(days=days)) if days else None
        sub.comp_reason = (reason or "").strip()[:255] or None
        sub.comped_by = admin_id
        db.session.commit()
        return sub.to_dict()

    def revoke_comp(self, user_id: int) -> dict:
        """Withdraw an administrator grant.

        Refuses when the account's access comes from a live Stripe subscription.
        Clearing our row without cancelling at Stripe would keep taking the
        user's money while denying them the product — a billing complaint, not
        a bug report. The administrator is pointed at the Stripe dashboard, or
        the user at the customer portal, instead.
        """
        sub = Subscription.query.filter_by(user_id=user_id).first()
        if sub is None:
            raise ValueError("That account has no subscription record.")
        if sub.stripe_subscription_id:
            raise ValueError(
                "That account is on a live Stripe subscription, so revoking it "
                "here would leave them being billed for access they no longer "
                "have. Cancel the subscription in the Stripe dashboard (or have "
                "the user cancel from their billing page) instead."
            )
        sub.status = "none"
        sub.comped_until = None
        sub.comp_reason = None
        sub.comped_by = None
        db.session.commit()
        return sub.to_dict()

    # ── summaries ──────────────────────────────────────────────────────────

    def summary_for_users(self, users: list) -> dict:
        """{user_id: entitlement} for a list of user dicts, in one query.

        The admin page shows a state badge per row. Calling entitlement() in a
        loop would be one SELECT per user.
        """
        if not users:
            return {}
        ids = [u["id"] for u in users]
        rows = {s.user_id: s for s in
                Subscription.query.filter(Subscription.user_id.in_(ids)).all()}
        now = datetime.utcnow()
        billing_on = current_app.config.get("BILLING_ENABLED")

        out = {}
        for u in users:
            if u.get("role") == "admin":
                out[u["id"]] = self._envelope(active=True, state="admin",
                                              plan="pro")
                continue
            if not billing_on:
                out[u["id"]] = self._envelope(active=True, state="comped",
                                              plan=self.plan_for_role(u.get("role")))
                continue
            sub = rows.get(u["id"])
            if sub is None:
                out[u["id"]] = self._envelope(
                    active=False, state="none",
                    plan=self.plan_for_role(u.get("role")))
                continue
            state = self._state(sub, now)
            out[u["id"]] = self._envelope(
                active=self._is_active(sub, now),
                state=state,
                plan=sub.plan,
                trial_ends_at=sub.trial_ends_at,
                trial_days_left=self._days_left(sub.trial_ends_at, now)
                                if state == "trialing" else None,
                current_period_end=sub.current_period_end,
                cancel_at_period_end=bool(sub.cancel_at_period_end),
                manageable=bool(sub.stripe_subscription_id),
                comped_until=sub.comped_until,
                comp_reason=sub.comp_reason,
            )
        return out

    def plans_display(self) -> dict:
        """Both plans and their prices, for the billing page."""
        return {plan: self.price_display(plan) for plan in VALID_PLANS}

    # ── Stripe ─────────────────────────────────────────────────────────────

    def _stripe(self):
        """The configured Stripe client module.

        The API version is pinned here rather than left to the account default.
        Without it, changing the default version in the Stripe dashboard would
        alter the shape of webhook payloads with no deploy and no warning — the
        handlers below read specific fields off those objects.
        """
        import stripe
        key = current_app.config.get("STRIPE_SECRET_KEY")
        if not key:
            raise ValueError("STRIPE_SECRET_KEY is not configured.")
        stripe.api_key = key
        stripe.api_version = STRIPE_API_VERSION
        return stripe

    def _customer_id(self, user: dict, sub: Subscription) -> str:
        """This account's Stripe customer, created on first use.

        `metadata.user_id` is set at creation because it is the first thing the
        webhook looks at to find the account a Stripe object belongs to — and it
        is the only link that survives the user changing their email.
        """
        if sub.stripe_customer_id:
            return sub.stripe_customer_id
        stripe = self._stripe()
        customer = stripe.Customer.create(
            email=user["email"],
            metadata={"user_id": str(user["id"]), "role": user["role"]},
        )
        sub.stripe_customer_id = customer["id"]
        db.session.commit()
        return customer["id"]

    def start_checkout(self, user: dict) -> str:
        """Create a Checkout session and return the URL to send the user to."""
        base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
        if not base:
            raise ValueError(
                "PUBLIC_BASE_URL is not configured, so there is nowhere to "
                "return the user to after payment.")
        # Price comes from the role, never from the request. This is the whole
        # tamper defence: a client that could name its own price id could buy
        # the £10 plan while registering as a coach.
        price_id, plan = self.price_for_role(user["role"])
        sub = self.get_for_user(user["id"], user["role"])
        if sub is None:
            raise ValueError("That account has no subscription record.")

        stripe = self._stripe()
        customer_id = self._customer_id(user, sub)
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            # Two independent ways back to the account: the webhook prefers
            # subscription metadata, and falls back to this.
            client_reference_id=str(user["id"]),
            subscription_data={"metadata": {"user_id": str(user["id"]),
                                            "plan": plan}},
            success_url=f"{base}/billing?checkout=success",
            cancel_url=f"{base}/billing?checkout=cancelled",
            allow_promotion_codes=True,
        )
        sub.stripe_price_id = price_id
        sub.plan = plan
        db.session.commit()
        return session["url"]

    def portal_url(self, user: dict) -> str:
        """A Stripe customer-portal session.

        Cancellation, card updates, invoices and receipts all live there, so
        none of that has to be built, and none of it ever touches card data
        here.
        """
        base = (current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
        if not base:
            raise ValueError("PUBLIC_BASE_URL is not configured.")
        sub = self.get_for_user(user["id"], user["role"])
        if sub is None or not sub.stripe_customer_id:
            raise ValueError("There is no billing account to manage yet.")
        stripe = self._stripe()
        session = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=f"{base}/billing",
        )
        return session["url"]

    def apply_stripe_subscription(self, obj: dict) -> Subscription | None:
        """Map a Stripe subscription object onto our row.

        Every webhook handler goes through here, so there is one mapping to get
        right rather than one per event type.
        """
        sub = self._find_row(obj)
        if sub is None:
            return None

        sub.stripe_subscription_id = obj.get("id") or sub.stripe_subscription_id
        customer = obj.get("customer")
        if customer and not sub.stripe_customer_id:
            sub.stripe_customer_id = customer

        status = obj.get("status")
        if status in VALID_STATUSES:
            sub.status = status
        sub.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
        sub.current_period_end = _ts(obj.get("current_period_end"))

        # Record what they are actually being charged, for audit. Never read back
        # to decide entitlement.
        items = ((obj.get("items") or {}).get("data") or [])
        if items:
            price = items[0].get("price") or {}
            if price.get("id"):
                sub.stripe_price_id = price["id"]

        # A paid subscription ends the local trial, whatever its date said.
        if sub.status in ("active", "past_due"):
            sub.trial_ends_at = None

        db.session.commit()
        return sub

    def _find_row(self, obj: dict) -> Subscription | None:
        """Locate the account a Stripe object belongs to.

        In order: subscription metadata, then our stored customer id, then the
        Checkout session's client_reference_id. Never by email — an email is
        editable at both ends and two accounts could share one.
        """
        meta = obj.get("metadata") or {}
        uid = meta.get("user_id")
        if uid:
            try:
                row = Subscription.query.filter_by(user_id=int(uid)).first()
                if row:
                    return row
            except (TypeError, ValueError):
                pass

        sub_id = obj.get("id")
        if sub_id:
            row = Subscription.query.filter_by(stripe_subscription_id=sub_id).first()
            if row:
                return row

        customer = obj.get("customer")
        if customer:
            row = Subscription.query.filter_by(stripe_customer_id=customer).first()
            if row:
                return row

        ref = obj.get("client_reference_id")
        if ref:
            try:
                return Subscription.query.filter_by(user_id=int(ref)).first()
            except (TypeError, ValueError):
                return None
        return None

    def mark_status(self, obj: dict, status: str) -> Subscription | None:
        """Set a status on the row a Stripe object points at, without a full map."""
        sub = self._find_row(obj)
        if sub is None:
            return None
        if status in VALID_STATUSES:
            sub.status = status
        db.session.commit()
        return sub

    def refresh_from_stripe(self, subscription_id: str) -> Subscription | None:
        """Retrieve a subscription from Stripe and apply it.

        Used by checkout.session.completed, which carries only the id.
        """
        if not subscription_id:
            return None
        stripe = self._stripe()
        obj = stripe.Subscription.retrieve(subscription_id)
        # retrieve() hands back a StripeObject, and `.get` on one raises
        # AttributeError rather than returning None. apply_stripe_subscription
        # reads it as a mapping, so convert first. to_dict() is deep enough —
        # the nested items list comes back as plain dicts — and unlike
        # to_dict_recursive it exists in the pinned SDK.
        return self.apply_stripe_subscription(obj.to_dict())

    def cancel_stripe_subscription(self, user_id: int) -> bool:
        """Cancel immediately at Stripe. Called before an account is deleted.

        Without this, deleting a user cascades their subscriptions row away and
        Stripe carries on billing somebody whose data has just been erased —
        both a money bug and a GDPR one.

        Returns True if something was cancelled. Failure is reported to the
        caller rather than raised: an erasure request must not be blocked by a
        Stripe outage.
        """
        sub = Subscription.query.filter_by(user_id=user_id).first()
        if sub is None or not sub.stripe_subscription_id:
            return False
        stripe = self._stripe()
        stripe.Subscription.delete(sub.stripe_subscription_id)
        return True


def _ts(value):
    """A Stripe unix timestamp as a naive UTC datetime.

    Naive on purpose: every datetime column in this schema is written by
    datetime.utcnow(), so storing a tz-aware value here would make the
    comparisons in _is_active raise TypeError on the first renewal.
    """
    if not value:
        return None
    try:
        return datetime.utcfromtimestamp(int(value))
    except (TypeError, ValueError, OSError):
        return None
