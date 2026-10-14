"""Account routes, under /api/auth/...

  POST   /register           create an account and sign in
  POST   /login | /logout
  GET    /me                 the signed-in user + entitlement (read at app boot)
  GET    /legal              current terms/privacy versions and acceptance state
  POST   /accept-terms       re-accept after a document changes
  POST   /link-fighter       claim a fighter profile (fighters only)
  PUT    /privacy            hide or show your fight record
  GET|POST|DELETE /deletion-request   request (or cancel) account erasure
  POST   /change-password

The session cookie stores only `user_id`; current_user() reloads the rest.
"""

from flask import Blueprint, jsonify, request, session, current_app
from flask_limiter.util import get_remote_address
from ..helpers import err, require_json, current_user, login_required, clean_str, get_db
from ..extensions import limiter
from ..legal import (
    TERMS_VERSION, PRIVACY_VERSION, COOKIE_POLICY_VERSION, MINIMUM_AGE,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _start_session(user: dict) -> None:
    """Sign `user` in. Sessions last PERMANENT_SESSION_LIFETIME (8h)."""
    session.permanent = True
    session["user_id"] = user["id"]


def _with_fighter_record(user: dict) -> dict:
    """For a fighter, attach their active profile as `fighter_record`."""
    if user["role"] == "fighter" and user["fighter_id"] and user["fighter_sport"]:
        try:
            with get_db(user["fighter_sport"]) as db:
                user["fighter_record"] = db.get_fighter(user["fighter_id"])
        except Exception:
            user["fighter_record"] = None
    return user


def _user_response(user: dict, status: int = 200):
    """The standard {user, entitlement} body returned after sign-in."""
    return jsonify({
        "user": user,
        "entitlement": current_app.billing_db.entitlement(user),
    }), status


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5 per hour")
def register():
    """Create an account and sign straight in. `accept_terms` must be true."""
    data, error = require_json("email", "password", "role")
    if error:
        return error
    # Consent must be a literal `true`; a missing field or "false" is a refusal.
    if data.get("accept_terms") is not True:
        return err("You must accept the terms and privacy notice to create an account.")
    try:
        user = current_app.auth_db.register(
            email=data["email"],
            password=data["password"],
            role=data["role"],
            accept_terms=True,
            # The service discards this for non-fighter roles.
            gender=clean_str(data.get("gender")),
        )
        if data["role"] == "fighter" and data.get("fighter_id") and data.get("fighter_sport"):
            user = current_app.auth_db.link_fighter(
                user["id"], int(data["fighter_id"]), data["fighter_sport"]
            )
        _start_session(user)
        return _user_response(user, 201)
    except ValueError as e:
        return err(str(e))


@auth_bp.route("/legal", methods=["GET"])
@auth_bp.route("/terms", methods=["GET"])   # pre-split name, kept for clients
def legal():
    """Current document versions, and whether the signed-in user is up to date
    with them. The wording itself is bundled with the frontend.

    `version` and `accepted` are older aliases of `terms_version` and
    `terms_accepted`, kept for older clients.
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
    """Re-accept after either document changes (registration records the
    first acceptance itself)."""
    try:
        return jsonify({"user": current_app.auth_db.accept_terms(current_user()["id"])})
    except ValueError as e:
        return err(str(e))


def _login_email_key():
    """Rate-limit key for the account being signed in to, not the caller.

    Caps attempts against one account no matter how many IP addresses they
    come from (the per-IP limit alone would not). Falls back to the caller's
    IP when the body has no usable email.
    """
    data = request.get_json(silent=True) or {}
    email = data.get("email") if isinstance(data, dict) else None
    if not isinstance(email, str) or not email.strip():
        return get_remote_address()
    return f"login-email:{email.strip().lower()[:254]}"


# Login limits: 5 failed attempts per 15 minutes, counted in two buckets (per
# IP and per account); a sign-in must pass both. Only failures count, so a
# successful sign-in never locks anyone out.
_LOGIN_FAILED_ONLY = lambda response: response.status_code != 200   # noqa: E731


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("5 per 15 minutes", deduct_when=_LOGIN_FAILED_ONLY)
@limiter.limit("5 per 15 minutes", key_func=_login_email_key,
               deduct_when=_LOGIN_FAILED_ONLY)
def login():
    """Sign in with email and password."""
    data, error = require_json("email", "password")
    if error:
        return error
    try:
        user = current_app.auth_db.login(data["email"], data["password"])
    except ValueError as e:
        return err(str(e), 401)
    _start_session(user)
    return _user_response(_with_fighter_record(user))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Clear the session."""
    session.clear()
    return jsonify({"message": "Logged out."})


@auth_bp.route("/me", methods=["GET"])
def me():
    """The signed-in user. The SPA calls this at boot; the entitlement tells
    it whether to show editing controls."""
    user = current_user()
    if not user:
        return err("Not logged in.", 401)
    return _user_response(_with_fighter_record(user))


@auth_bp.route("/link-fighter", methods=["POST"])
@login_required
def link_fighter():
    """Claim an existing fighter profile for this (fighter) account."""
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
    """Body: {"hide_record": bool}."""
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
@limiter.limit("10 per hour")
def create_deletion_request():
    """Ask for this account to be erased (password required).

    The rate limit only bounds password guessing; it is deliberately loose so
    a couple of typos never block someone exercising their erasure right.
    """
    data, error = require_json("password")
    if error:
        return error
    try:
        req = current_app.auth_db.request_deletion(
            current_user()["id"],
            password=data["password"],
            # Optional by design: nobody has to justify an erasure request.
            reason=clean_str(data.get("reason"), max_len=1000),
        )
        return jsonify({"request": req}), 201
    except ValueError as e:
        return err(str(e))


@auth_bp.route("/deletion-request", methods=["DELETE"])
@login_required
def cancel_deletion_request():
    """Withdraw a pending erasure request."""
    try:
        current_app.auth_db.cancel_deletion(current_user()["id"])
        return jsonify({"message": "Deletion request cancelled."})
    except ValueError as e:
        return err(str(e))


@auth_bp.route("/change-password", methods=["POST"])
@login_required
@limiter.limit("5 per 15 minutes", deduct_when=_LOGIN_FAILED_ONLY)
def change_password():
    """Change password. Rate-limited like login, since it checks a password."""
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
