from flask import Blueprint, jsonify, request, session, current_app
from flask_limiter.util import get_remote_address
from ..helpers import err, require_json, current_user, login_required, clean_str
from ..extensions import limiter
from ..legal import (
    TERMS_VERSION, PRIVACY_VERSION, COOKIE_POLICY_VERSION, MINIMUM_AGE,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
# Per hour, not per minute: nobody legitimately creates five accounts in an
# hour from one address, and the old per-minute window let a script open
# hundreds a day while never once tripping it.
@limiter.limit("5 per hour")
def register():
    data, error = require_json("email", "password", "role")
    if error:
        return error
    # Consent must be a positive act, so only a literal true counts. Sending
    # no field at all, "false", or a truthy-looking string is a refusal.
    if data.get("accept_terms") is not True:
        return err("You must accept the terms and privacy notice to create an account.")
    try:
        user = current_app.auth_db.register(
            email=data["email"],
            password=data["password"],
            role=data["role"],
            accept_terms=True,
            # Only asked of fighters; the service discards it for every other
            # role rather than trusting the form to have hidden the field.
            gender=clean_str(data.get("gender")),
        )
        if data["role"] == "fighter" and data.get("fighter_id") and data.get("fighter_sport"):
            user = current_app.auth_db.link_fighter(
                user["id"], int(data["fighter_id"]), data["fighter_sport"]
            )
        session.permanent = True     # honour PERMANENT_SESSION_LIFETIME (8h)
        session["user_id"] = user["id"]
        # A sibling key, not nested inside `user`: User.to_dict() stays a pure
        # model serialiser, and nothing that already reads `user` has to change.
        return jsonify({
            "user": user,
            "entitlement": current_app.billing_db.entitlement(user),
        }), 201
    except ValueError as e:
        return err(str(e))


@auth_bp.route("/legal", methods=["GET"])
@auth_bp.route("/terms", methods=["GET"])   # pre-split name, kept for clients
def legal():
    """Current document versions, and whether the signed-in user is up to date
    with them. The wording itself is bundled with the frontend.

    `accepted` stays in the response under its old meaning — agreement to the
    terms — so a client from before the split keeps working through a rolling
    deploy.
    """
    user = current_user()
    terms_ok   = bool(user and user.get("terms_version") == TERMS_VERSION)
    privacy_ok = bool(user and user.get("privacy_version") == PRIVACY_VERSION)
    return jsonify({
        "version":         TERMS_VERSION,
        "terms_version":   TERMS_VERSION,
        "privacy_version": PRIVACY_VERSION,
        "cookie_policy_version": COOKIE_POLICY_VERSION,
        "minimum_age":     MINIMUM_AGE,
        "accepted":        terms_ok,
        "terms_accepted":  terms_ok,
        "privacy_accepted": privacy_ok,
        # One flag for the UI to act on, so the prompt logic does not have to
        # be reimplemented per document on the client.
        "reacceptance_required": bool(user) and not (terms_ok and privacy_ok),
    })


@auth_bp.route("/accept-terms", methods=["POST"])
@login_required
def accept_terms():
    """Re-accept after either document changes. Registration records agreement
    on its own; this exists only for accounts that predate the current
    versions."""
    try:
        return jsonify({"user": current_app.auth_db.accept_terms(current_user()["id"])})
    except ValueError as e:
        return err(str(e))


def _login_email_key():
    """Rate-limit key for the account being signed in to, not the caller.

    The IP limit alone is not enough: an attacker with a pool of addresses gets
    five attempts per address against one account, which is no limit at all on
    the thing that matters. This bucket caps attempts against a single account
    however many places they come from.

    Falls back to the remote address when there is no usable email, so a
    malformed body cannot slip past by omitting the field.
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email") if isinstance(data, dict) else None
    if not isinstance(email, str) or not email.strip():
        return get_remote_address()
    return f"login-email:{email.strip().lower()[:254]}"


# Five attempts, as a deliberate ceiling rather than a throttle: enough for a
# mistyped password and a forgotten capital, far short of useful guessing.
#
# Two buckets — one per caller, one per account — and the sign-in has to pass
# both. Successful sign-ins are not counted (deduct_when), so someone who gets
# it right on the fifth try is not then locked out for the next quarter of an
# hour by their own success.
_LOGIN_FAILED_ONLY = lambda response: response.status_code != 200   # noqa: E731


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per 15 minutes", deduct_when=_LOGIN_FAILED_ONLY)
@limiter.limit("5 per 15 minutes", key_func=_login_email_key,
               deduct_when=_LOGIN_FAILED_ONLY)
def login():
    data, error = require_json("email", "password")
    if error:
        return error
    try:
        user = current_app.auth_db.login(data["email"], data["password"])
        session.permanent = True     # honour PERMANENT_SESSION_LIFETIME (8h)
        session["user_id"] = user["id"]
        if user["role"] == "fighter" and user["fighter_id"] and user["fighter_sport"]:
            try:
                from ..helpers import get_db
                with get_db(user["fighter_sport"]) as db:
                    user["fighter_record"] = db.get_fighter(user["fighter_id"])
            except Exception:
                user["fighter_record"] = None
        return jsonify({
            "user": user,
            "entitlement": current_app.billing_db.entitlement(user),
        })
    except ValueError as e:
        return err(str(e), 401)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@auth_bp.route("/me", methods=["GET"])
def me():
    user = current_user()
    if not user:
        return err("Not logged in.", 401)
    if user["role"] == "fighter" and user["fighter_id"] and user["fighter_sport"]:
        try:
            from ..helpers import get_db
            with get_db(user["fighter_sport"]) as db:
                user["fighter_record"] = db.get_fighter(user["fighter_id"])
        except Exception:
            user["fighter_record"] = None
    # The SPA reads this once at boot, so it is where the frontend learns whether
    # to render write affordances at all.
    return jsonify({
        "user": user,
        "entitlement": current_app.billing_db.entitlement(user),
    })


@auth_bp.route("/link-fighter", methods=["POST"])
@login_required
def link_fighter():
    user = current_user()
    if user["role"] != "fighter":
        return err("Only fighters can link their accounts.", 403)
    data, error = require_json("fighter_id", "fighter_sport")
    if error:
        return error
    try:
        updated = current_app.auth_db.link_fighter(
            user["id"], int(data["fighter_id"]), data["fighter_sport"]
        )
        return jsonify({"user": updated})
    except ValueError as e:
        return err(str(e))


@auth_bp.route("/privacy", methods=["PUT"])
@login_required
def update_privacy():
    data = request.get_json(silent=True) or {}
    hide = bool(data.get("hide_record", False))
    try:
        updated = current_app.auth_db.update_privacy(current_user()["id"], hide)
        return jsonify({"user": updated})
    except ValueError as e:
        return err(str(e))


@auth_bp.route("/deletion-request", methods=["GET"])
@login_required
def get_deletion_request():
    """The signed-in account's pending erasure request, if any."""
    return jsonify({"request": current_app.auth_db.get_deletion_request(current_user()["id"])})


@auth_bp.route("/deletion-request", methods=["POST"])
@login_required
# Bounds the password check on this route, nothing more. Deliberately not
# tighter: the service already refuses a second pending request, so this is not
# what stops the queue being spammed, and a limit low enough to be tripped by
# two mistyped passwords would obstruct someone exercising an erasure right —
# which is the one thing a rights procedure must not do.
@limiter.limit("10 per hour")
def create_deletion_request():
    data, error = require_json("password")
    if error:
        return error
    try:
        req = current_app.auth_db.request_deletion(
            current_user()["id"],
            password=data["password"],
            # Optional, and it stays optional: nobody has to justify asking for
            # their own data back.
            reason=clean_str(data.get("reason"), max_len=1000),
        )
        return jsonify({"request": req}), 201
    except ValueError as e:
        return err(str(e))


@auth_bp.route("/deletion-request", methods=["DELETE"])
@login_required
def cancel_deletion_request():
    try:
        current_app.auth_db.cancel_deletion(current_user()["id"])
        return jsonify({"message": "Deletion request cancelled."})
    except ValueError as e:
        return err(str(e))


@auth_bp.route("/change-password", methods=["POST"])
@login_required
# Same ceiling as sign-in: this route also verifies a password, so it is the
# other place an attacker on a borrowed session can guess one.
@limiter.limit("5 per 15 minutes", deduct_when=_LOGIN_FAILED_ONLY)
def change_password():
    data, error = require_json("old_password", "new_password")
    if error:
        return error
    try:
        current_app.auth_db.change_password(
            current_user()["id"], data["old_password"], data["new_password"]
        )
        return jsonify({"message": "Password changed successfully."})
    except ValueError as e:
        return err(str(e))
