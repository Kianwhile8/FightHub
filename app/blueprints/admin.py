"""Admin-only routes, under /api/admin/...

  GET    /users                                every account + its entitlement
  PUT    /users/<id>/role                      change role
  DELETE /users/<id>                           erase an account immediately
  POST   /users/<id>/subscription/grant        comp an account (optionally for N days)
  POST   /users/<id>/subscription/revoke       withdraw a comp
  GET    /billing/events                       recent Stripe webhook deliveries
  GET    /deletion-requests                    erasure queue (?status=, default pending)
  POST   /deletion-requests/<id>/complete|reject
"""

from flask import Blueprint, jsonify, request, current_app
from ..helpers import err, current_user, roles_required, clean_str
from ..validation import clean_int
from ..models.subscription import WebhookEvent

admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@admin_bp.route("/users", methods=["GET"])
@roles_required("admin")
def list_users():
    """Every account, plus {user_id: entitlement} fetched in one query."""
    users = current_app.auth_db.get_all_users()
    return jsonify({
        "users": users,
        "entitlements": current_app.billing_db.summary_for_users(users),
    })


@admin_bp.route("/users/<int:user_id>/role", methods=["PUT"])
@roles_required("admin")
def update_role(user_id):
    """Body: {"role": "fighter" | "coach" | "promoter" | "admin"}."""
    data = request.get_json(silent=True) or {}
    if "role" not in data:
        return err("Missing field: role")
    try:
        updated = current_app.auth_db.update_role(user_id, data["role"])
        return jsonify({"user": updated})
    except ValueError as e:
        return err(str(e))


@admin_bp.route("/users/<int:user_id>", methods=["DELETE"])
@roles_required("admin")
def delete_user(user_id):
    """Erase an account now (admins cannot delete themselves)."""
    if user_id == current_user()["id"]:
        return err("Cannot delete your own account.")
    try:
        current_app.auth_db.delete_user(user_id)
        return jsonify({"deleted": user_id})
    except ValueError as e:
        return err(str(e), 404)


@admin_bp.route("/users/<int:user_id>/subscription/grant", methods=["POST"])
@roles_required("admin")
def grant_subscription(user_id):
    """Give an account access without a Stripe subscription.

    For comps, bank transfers, and anyone who should not be charged. `days`
    omitted or null means indefinitely.
    """
    data = request.get_json(silent=True) or {}
    days = data.get("days")
    if days is not None:
        days = clean_int(days, "days", minimum=1, maximum=3650)
    try:
        return jsonify({
            "subscription": current_app.billing_db.grant_comp(
                user_id,
                admin_id=current_user()["id"],
                days=days,
                reason=clean_str(data.get("reason"), max_len=255),
            ),
        })
    except ValueError as e:
        return err(str(e))


@admin_bp.route("/users/<int:user_id>/subscription/revoke", methods=["POST"])
@roles_required("admin")
def revoke_subscription(user_id):
    """Withdraw a comp. Refused if the account is on a live Stripe
    subscription (see BillingService.revoke_comp)."""
    try:
        return jsonify({
            "subscription": current_app.billing_db.revoke_comp(user_id),
        })
    except ValueError as e:
        return err(str(e))


@admin_bp.route("/billing/events", methods=["GET"])
@roles_required("admin")
def list_billing_events():
    """The 50 most recent Stripe webhook deliveries (optionally ?status=),
    for diagnosing payments that did not apply."""
    status = clean_str(request.args.get("status"))
    query = WebhookEvent.query
    if status:
        query = query.filter_by(status=status)
    rows = query.order_by(WebhookEvent.received_at.desc()).limit(50).all()
    return jsonify({"events": [r.to_dict() for r in rows]})


@admin_bp.route("/deletion-requests", methods=["GET"])
@roles_required("admin")
def list_deletion_requests():
    """The erasure queue. Defaults to what still needs doing."""
    status = clean_str(request.args.get("status"), default="pending")
    if status == "all":
        status = None
    return jsonify({
        "requests": current_app.auth_db.list_deletion_requests(status),
    })


@admin_bp.route("/deletion-requests/<int:request_id>/<action>", methods=["POST"])
@roles_required("admin")
def resolve_deletion_request(request_id, action):
    """Complete or reject one request.

    Completing it erases the account, irreversibly. Rejecting requires a
    note giving the reason.
    """
    if action not in ("complete", "reject"):
        return err("Action must be 'complete' or 'reject'.", 404)
    data = request.get_json(silent=True) or {}
    try:
        resolved = current_app.auth_db.resolve_deletion_request(
            request_id,
            admin_id=current_user()["id"],
            action=action,
            note=clean_str(data.get("note"), max_len=1000),
        )
        return jsonify({"request": resolved})
    except ValueError as e:
        return err(str(e))
