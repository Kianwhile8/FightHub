"""Billing: subscription status, Stripe Checkout, the customer portal and the
webhook.

Everything Stripe is server-side. No Stripe JavaScript is ever loaded in the
browser, which is what keeps `script-src 'self'` intact and keeps the privacy
notice's "loads nothing from any external server" true of the pages we serve.

The CSP shapes this implementation in three ways worth knowing before changing
anything here:

  * `frame-src 'none'` rules out embedded Checkout and Stripe Elements, so this
    is redirect-only.
  * `form-action 'self'` means the redirect must be a scripted navigation
    (window.location.assign), not a form POST at checkout.stripe.com.
  * `connect-src 'self'` means the browser cannot call api.stripe.com directly,
    which is the point: it never needs to.
"""

import json
from datetime import datetime

from flask import Blueprint, jsonify, request, current_app

from ..helpers import err, login_required, current_user
from ..extensions import limiter, csrf, db
from ..models.subscription import WebhookEvent

billing_bp = Blueprint("billing", __name__, url_prefix="/api/billing")

# The events this app acts on. Anything else is recorded and ignored, so a
# dashboard subscribed to more than this does not produce retry storms.
HANDLED_EVENTS = (
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.paid",
    "invoice.payment_failed",
    "charge.refunded",
    "charge.dispute.created",
)


def _billing_off():
    """503 when the feature is switched off, so the UI can tell this apart from
    a misconfiguration or a refusal."""
    return jsonify({
        "error": "Subscriptions are not enabled on this deployment.",
        "billing_enabled": False,
    }), 503


@billing_bp.route("/status", methods=["GET"])
@login_required
def status():
    """The signed-in user's entitlement (same envelope as /api/auth/me),
    plus both plans' prices."""
    user = current_user()
    return jsonify({
        "entitlement": current_app.billing_db.entitlement(user),
        "plans":       current_app.billing_db.plans_display(),
        "billing_enabled": bool(current_app.config.get("BILLING_ENABLED")),
        "trial_days":  current_app.config.get("TRIAL_DAYS", 7),
    })


@billing_bp.route("/checkout", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def checkout():
    """Start a Stripe Checkout session and hand back its URL.

    The request body is ignored: the price always comes from the user's role
    (BillingService.price_for_role), so a client cannot choose a cheaper one.
    """
    if not current_app.config.get("BILLING_ENABLED"):
        return _billing_off()

    user = current_user()
    if user["role"] == "admin":
        return err("Administrator accounts do not require a subscription.", 400)

    ent = current_app.billing_db.entitlement(user)
    # Already paying and not winding down: send them to manage it rather than
    # letting them buy a second subscription.
    if ent["state"] == "active" and not ent["cancel_at_period_end"]:
        try:
            return jsonify({
                "error": "That account already has an active subscription.",
                "portal_url": current_app.billing_db.portal_url(user),
            }), 409
        except ValueError as exc:
            return err(str(exc), 409)

    try:
        return jsonify({"url": current_app.billing_db.start_checkout(user)})
    except ValueError as exc:
        return err(str(exc), 400)
    except Exception:
        current_app.logger.exception("stripe checkout failed for user %s", user["id"])
        return err("Could not start checkout. Please try again shortly.", 502)


@billing_bp.route("/portal", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def portal():
    """A Stripe customer-portal session: cancel, update card, see invoices."""
    if not current_app.config.get("BILLING_ENABLED"):
        return _billing_off()
    user = current_user()
    try:
        return jsonify({"url": current_app.billing_db.portal_url(user)})
    except ValueError as exc:
        return err(str(exc), 409)
    except Exception:
        current_app.logger.exception("stripe portal failed for user %s", user["id"])
        return err("Could not open the billing portal. Please try again shortly.", 502)


@billing_bp.route("/webhook", methods=["POST"])
@csrf.exempt     # Stripe cannot send a CSRF token; the signature check replaces it
@limiter.exempt  # Stripe bursts when retrying; a 429 only causes more retries
def webhook():
    """Apply a Stripe event to the subscription it concerns.

    Steps: verify the signature -> record the event (idempotency) -> apply it
    (_apply) -> mark it processed.

    Returns 200 for anything safely recorded, including event types we ignore,
    so Stripe stops retrying. 500 only for failures worth retrying.
    """
    if not current_app.config.get("BILLING_ENABLED"):
        # 200, not 503: a disabled deployment should not make Stripe retry for
        # three days.
        return "", 200

    secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
    if not secret:
        current_app.logger.error("stripe webhook received but STRIPE_WEBHOOK_SECRET is unset")
        return "", 500

    raw = request.get_data()
    try:
        import stripe
        # The RAW bytes, not request.get_json(): the signature is computed over
        # exactly what Stripe sent, and reparsing and re-serialising it changes
        # the bytes and fails verification.
        stripe.Webhook.construct_event(
            raw, request.headers.get("Stripe-Signature", ""), secret)
        # Read the (now verified) bytes as plain JSON, because `.get` on the
        # StripeObject construct_event returns raises AttributeError.
        event = json.loads(raw)
    except ValueError:
        # Unparseable body.
        return "", 400
    except Exception:
        # Includes SignatureVerificationError. Write nothing: an unverified
        # payload is an unauthenticated caller claiming to be Stripe.
        return "", 400

    event_id = event.get("id")
    event_type = event.get("type") or "unknown"
    obj = ((event.get("data") or {}).get("object")) or {}

    # ── idempotency ────────────────────────────────────────────────────────
    # Insert first and commit, then process, then mark processed. Stripe
    # delivers at-least-once, so without this a retried invoice.paid is applied
    # twice.
    existing = WebhookEvent.query.filter_by(stripe_event_id=event_id).first()
    if existing:
        if existing.status == "processed":
            return "", 200
        # 'received' or 'failed' means a previous attempt began and did not
        # finish, so this delivery should be processed rather than dropped.
        record = existing
    else:
        record = WebhookEvent(
            stripe_event_id=event_id,
            event_type=event_type,
            status="received",
            payload_summary=_summarise(event, obj),
        )
        db.session.add(record)
        try:
            db.session.commit()
        except Exception:
            # Another instance inserted the same event id between our check and
            # our insert. That instance owns it.
            db.session.rollback()
            return "", 200

    if event_type not in HANDLED_EVENTS:
        record.status = "ignored"
        record.processed_at = datetime.utcnow()
        db.session.commit()
        return "", 200

    try:
        _apply(event_type, obj)
        record.status = "processed"
        record.processed_at = datetime.utcnow()
        record.error = None
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("stripe webhook %s (%s) failed",
                                     event_id, event_type)
        record.status = "failed"
        record.error = f"{type(exc).__name__}: {exc}"[:2000]
        db.session.commit()
        # 500 so Stripe retries — this one may well succeed next time.
        return "", 500

    return "", 200


def _apply(event_type: str, obj: dict) -> None:
    """Update our Subscription row for one handled Stripe event type."""
    billing = current_app.billing_db

    if event_type == "checkout.session.completed":
        # The first signal that money has moved, and usually the only one that
        # has arrived by the time the browser gets back to /billing. The session
        # carries only the subscription's id, so retrieve the real object.
        billing.refresh_from_stripe(obj.get("subscription"))
        return

    if event_type in ("customer.subscription.created",
                      "customer.subscription.updated"):
        # Renewals, plan changes, cancel_at_period_end being toggled, and the
        # transition out of a trial all arrive as 'updated'.
        billing.apply_stripe_subscription(obj)
        return

    if event_type == "customer.subscription.deleted":
        billing.mark_status(obj, "canceled")
        return

    if event_type == "invoice.paid":
        # Refresh the period end from the subscription the invoice belongs to.
        billing.refresh_from_stripe(obj.get("subscription"))
        return

    if event_type == "invoice.payment_failed":
        sub_id = obj.get("subscription")
        if sub_id:
            # Keeps access — see BillingService._is_active. Stripe retries for
            # about three weeks, and this only drives the in-app warning.
            billing.mark_status({"id": sub_id}, "past_due")
        return

    if event_type in ("charge.refunded", "charge.dispute.created"):
        # Recorded only, deliberately. Access is NOT revoked automatically: a
        # dispute over £20 is a conversation plus the admin revoke button, and
        # auto-revoking would punish a customer whose bank flagged a card.
        return


def _summarise(event: dict, obj: dict) -> str:
    """A trimmed record of the event: ids and status only.

    Never the raw payload, which contains the customer's email and address.
    """
    return json.dumps({
        "id":        event.get("id"),
        "type":      event.get("type"),
        "created":   event.get("created"),
        "object_id": obj.get("id"),
        "customer":  obj.get("customer"),
        "subscription": obj.get("subscription"),
        "status":    obj.get("status"),
    }, separators=(",", ":"))[:2000]
