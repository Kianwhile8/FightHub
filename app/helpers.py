"""Shared request helpers used by every blueprint.

Sections:
  - responses and request parsing   (err, require_json)
  - authentication and roles        (current_user, login_required, roles_required)
  - billing entitlement             (has_active_access, subscription_required)
  - fighter privacy and ownership   (owns_profile, _apply_privacy, _coach_owns_fighter)
"""

import functools
from flask import jsonify, request, session, current_app, g

# Re-exported from .validation, which owns the one implementation, so
# blueprints can keep importing them from here. Keeping a single sanitiser
# avoids two copies drifting apart.
from .validation import clean_str, ValidationError  # noqa: F401
from .constants import VALID_SPORTS  # noqa: F401  (re-exported for blueprints)


def get_db(sport: str):
    """Return a FighterService for one sport. Use it as `with get_db(s) as db:`."""
    from .services.fighter_service import FighterService
    return FighterService(sport)


# ── responses and request parsing ─────────────────────────────────────────

def err(msg: str, status: int = 400):
    """A JSON error response: `{"error": msg}` with the given status."""
    return jsonify({"error": msg}), status


def require_json(*fields):
    """Parse the JSON body and check the named fields are present and non-empty.

    Returns `(data, None)` on success or `(None, error_response)` on failure,
    so a route can do:

        data, error = require_json("name", "weight")
        if error:
            return error
    """
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        # A JSON array or bare string parses fine and then fails on .get() with
        # an AttributeError several frames deeper.
        return None, err("Request body must be a JSON object.")
    missing = [f for f in fields if f not in data or data[f] in ("", None)]
    if missing:
        return None, err(f"Missing required fields: {', '.join(missing)}")
    return data, None


# ── authentication and roles ──────────────────────────────────────────────

def current_user() -> dict | None:
    """The logged-in user as a dict, or None if there is no valid session."""
    uid = session.get("user_id")
    if not uid:
        return None
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return None
    return current_app.auth_db.get_by_id(uid)


def login_required(f):
    """Route decorator: 401 unless someone is logged in."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return err("Login required.", 401)
        return f(*args, **kwargs)
    return wrapper


def roles_required(*roles):
    """Route decorator: 401 if logged out, 403 unless the user has one of `roles`."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                return err("Login required.", 401)
            if user["role"] not in roles:
                return err(f"Access denied. Required roles: {' or '.join(roles)}", 403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ── billing entitlement ───────────────────────────────────────────────────

def has_active_access(user) -> bool:
    """Is this account allowed to write (add, edit, matchmake)?

    This is the only place entitlement is decided. The answer is cached on
    `flask.g` for the rest of the request, because some handlers reach it
    several times through nested helpers.
    """
    if not user:
        return False
    # Billing kill switch, checked here and nowhere else. With billing off,
    # every gated route is open to everyone.
    if not current_app.config.get("BILLING_ENABLED"):
        return True
    if user["role"] == "admin":
        return True              # administrators never pay
    if not hasattr(g, "_entitlement"):
        g._entitlement = current_app.billing_db.entitlement(user)
    return g._entitlement["active"]


def payment_required():
    """A 402 response carrying `payment_required: true` and the entitlement.

    The flag follows the same convention as `csrf: true` on 419 responses.
    Including the entitlement lets the frontend switch every page to read-only
    on the first 402, without waiting for the next /api/auth/me.
    """
    ent = current_app.billing_db.entitlement(current_user())
    return jsonify({
        "error": "Your FightHub subscription has ended. Reading stays free — "
                 "adding, editing and matchmaking need an active subscription.",
        "payment_required": True,
        "entitlement": ent,
    }), 402


def subscription_required(f):
    """Gate a route on an active subscription.

    Always place this BELOW @roles_required, so that roles_required's wrapper
    runs first:

        @roles_required("coach", "admin")
        @subscription_required
        def add_fighter(sport): ...

    Decorators apply bottom-up. With that order a fighter hitting a coach-only
    route is told they have the wrong role (403), not asked to pay (402) for
    something their role could never do either way.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return err("Login required.", 401)
        if not has_active_access(user):
            return payment_required()
        return f(*args, **kwargs)
    return wrapper


# ── fighter privacy and ownership ─────────────────────────────────────────

def _mask_record(fighter: dict) -> dict:
    """Copy of `fighter` with its win/loss/draw record blanked out."""
    return {**fighter, "wins": None, "losses": None, "draws": None, "record_hidden": True}


def owns_profile(viewer, fighter: dict, sport: str) -> bool:
    """Is this fighter profile the viewer's own?

    Matches on the profile's owning account first, so someone who competes in
    more than one discipline still sees their own record on every profile they
    own. Falls back to the single legacy account link for profiles that were
    claimed before `Fighter.user_id` existed.
    """
    if not viewer:
        return False
    if fighter.get("user_id") and fighter["user_id"] == viewer["id"]:
        return True
    return (viewer.get("fighter_id") == fighter.get("id")
            and viewer.get("fighter_sport") == sport)


def _apply_privacy(fighters: list, sport: str, viewer) -> list:
    """Mask the records of fighters who chose to hide them.

    Admins and the fighter themselves still see the real record.
    """
    hidden = current_app.auth_db.get_hidden_fighter_ids(sport)
    if not hidden:
        return fighters
    is_admin = viewer and viewer["role"] == "admin"
    return [
        f if (is_admin or owns_profile(viewer, f, sport) or f["id"] not in hidden)
        else _mask_record(f)
        for f in fighters
    ]


def _coach_owns_fighter(sport: str, fighter_id: int, user: dict) -> bool:
    """True if `user` is an admin or coaches the gym this fighter belongs to."""
    if user["role"] == "admin":
        return True
    with get_db(sport) as db:
        fighter = db.get_fighter(fighter_id)
    if not fighter or not fighter.get("gym_id"):
        return False
    gym = current_app.auth_db.get_gym(fighter["gym_id"])
    return gym is not None and gym["coach_id"] == user["id"]
