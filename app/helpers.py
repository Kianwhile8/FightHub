import functools
from flask import jsonify, request, session, current_app, g

VALID_SPORTS = ("kickboxing", "mma", "boxing", "muaythai")


def get_db(sport: str):
    """Return a FighterService for the given sport (context-manager compatible)."""
    from .services.fighter_service import FighterService
    return FighterService(sport)


# Re-exported from .validation, which owns the one implementation. Kept here
# because every blueprint already imports it from helpers, and two copies of a
# sanitiser is how one of them ends up being the lenient one.
from .validation import clean_str, ValidationError  # noqa: E402,F401


def err(msg: str, status: int = 400):
    return jsonify({"error": msg}), status


def require_json(*fields):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        # A JSON array or bare string parses fine and then fails on .get() with
        # an AttributeError several frames deeper.
        return None, err("Request body must be a JSON object.")
    missing = [f for f in fields if f not in data or data[f] in ("", None)]
    if missing:
        return None, err(f"Missing required fields: {', '.join(missing)}")
    return data, None


def current_user() -> dict | None:
    uid = session.get("user_id")
    if not uid:
        return None
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        return None
    return current_app.auth_db.get_by_id(uid)


def login_required(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user():
            return err("Login required.", 401)
        return f(*args, **kwargs)
    return wrapper


def roles_required(*roles):
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


def has_active_access(user) -> bool:
    """Is this account entitled to write? The one truth function.

    Cached on `flask.g` for the request. The matchmaking handler alone makes
    several database round trips through nested helpers, and a decorator that
    added one query per call would be paying for the same answer repeatedly.
    """
    if not user:
        return False
    # The kill switch, checked here and nowhere else. With billing off the whole
    # feature is inert: every gated route behaves exactly as it did before, so
    # the code can ship and be deployed before a charge is possible.
    if not current_app.config.get("BILLING_ENABLED"):
        return True
    if user["role"] == "admin":
        return True              # administrators never pay
    if not hasattr(g, "_entitlement"):
        g._entitlement = current_app.billing_db.entitlement(user)
    return g._entitlement["active"]


def payment_required():
    """402, with a machine-readable discriminator and the current entitlement.

    `payment_required: true` mirrors the `csrf: true` convention the CSRF
    handler already uses at 419, so the frontend has one pattern for "this
    status code means something specific". Sending the entitlement back with the
    refusal lets the client flip every mounted page to read-only on the first
    402, without waiting for the next /api/auth/me.
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


def _mask_record(fighter: dict) -> dict:
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
    if user["role"] == "admin":
        return True
    with get_db(sport) as db:
        fighter = db.get_fighter(fighter_id)
    if not fighter or not fighter.get("gym_id"):
        return False
    gym = current_app.auth_db.get_gym(fighter["gym_id"])
    return gym is not None and gym["coach_id"] == user["id"]
