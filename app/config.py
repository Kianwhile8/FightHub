"""Configuration classes, read from environment variables (.env locally).

`Config` holds everything shared; `DevelopmentConfig` and `ProductionConfig`
differ only in cookie security. See .env.example for every variable.
"""

import os
from datetime import timedelta

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bool_env(name: str, default: bool) -> bool:
    """Read a boolean from the environment. Accepts 1/true/yes/on."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    """Read an integer from the environment, falling back to `default`."""
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI     = os.environ.get("DATABASE_URL")
    UPLOAD_FOLDER               = os.path.join(_root, "uploads")
    MAX_CONTENT_LENGTH          = 5 * 1024 * 1024  # 5 MB
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Waitress serves every request from one process, so this pool is shared by
    # all of its threads. Keep pool_size >= WAITRESS_THREADS or requests will
    # queue waiting for a free connection instead of for the database.
    # If this ever moves to a multi-process server (gunicorn), the real limit is
    # workers x (pool_size + max_overflow) < Postgres max_connections.
    SQLALCHEMY_ENGINE_OPTIONS   = {
        "pool_size":     _int_env("DB_POOL_SIZE", 10),
        "max_overflow":  _int_env("DB_MAX_OVERFLOW", 5),
        "pool_pre_ping": True,
        "pool_recycle":  1800,   # recycle before Postgres/proxies drop idle conns
    }

    # Mirrors what extensions.py passes to the Limiter at construction, so
    # check-deploy reports the limiter's real backend rather than a guess.
    RATELIMIT_STORAGE_URL = os.environ.get("RATELIMIT_STORAGE_URL", "memory://")

    # ── uploads ───────────────────────────────────────────────────────────
    # 'local' writes to UPLOAD_FOLDER; 'gcs' writes to a Cloud Storage bucket.
    # Cloud Run must use 'gcs' — its disk is per-instance and does not survive a
    # deploy, so local uploads silently vanish.
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "local").strip().lower()
    GCS_BUCKET      = os.environ.get("GCS_BUCKET")
    GCS_PREFIX      = os.environ.get("GCS_PREFIX", "uploads/")
    GCS_PUBLIC_URLS = _bool_env("GCS_PUBLIC_URLS", False)

    # ── outbound email (confirmation links, password resets) ──────────────
    # Not wired to an email provider yet. PUBLIC_BASE_URL is what verification links
    # are built from, so it must be the address users actually reach — behind a
    # proxy the app cannot reliably infer it from the request.
    PUBLIC_BASE_URL = (os.environ.get("PUBLIC_BASE_URL") or "").rstrip("/")
    MAIL_PROVIDER   = os.environ.get("MAIL_PROVIDER", "").strip().lower()
    MAIL_API_KEY    = os.environ.get("MAIL_API_KEY")
    MAIL_FROM       = os.environ.get("MAIL_FROM")
    REQUIRE_VERIFIED_EMAIL = _bool_env("REQUIRE_VERIFIED_EMAIL", False)

    # ── billing (Stripe) ──────────────────────────────────────────────────
    # Off by default, so the app can be deployed and tested before any charge
    # is possible. With it off, has_active_access() returns True for everybody
    # and /api/billing/* returns 503. The flag is checked in exactly one place:
    # has_active_access() in app/helpers.py.
    BILLING_ENABLED       = _bool_env("BILLING_ENABLED", False)
    STRIPE_SECRET_KEY     = os.environ.get("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
    # Price ids, not product ids. A `prod_...` here fails at session creation
    # with an unhelpful error; check-deploy retrieves both and verifies.
    STRIPE_PRICE_FIGHTER  = os.environ.get("STRIPE_PRICE_FIGHTER")
    STRIPE_PRICE_PRO      = os.environ.get("STRIPE_PRICE_PRO")

    # Free trial on every new account, run locally rather than in Stripe: it
    # starts at registration, before the user has a Stripe customer, and takes
    # no card.
    TRIAL_DAYS            = _int_env("TRIAL_DAYS", 7)
    # Grace after `current_period_end` before access is cut. Webhook delivery is
    # at-least-once and can lag, so a renewal Stripe has taken but not yet
    # announced must not lock a paying coach out.
    BILLING_GRACE_DAYS    = _int_env("BILLING_GRACE_DAYS", 2)

    # Display only — what the UI prints. The authority is the Stripe price, and
    # check-deploy fails if these disagree with it. They exist so a page can
    # show a price without a round trip to Stripe on every render.
    PRICE_FIGHTER_PENCE   = _int_env("PRICE_FIGHTER_PENCE", 1000)
    PRICE_PRO_PENCE       = _int_env("PRICE_PRO_PENCE", 2000)
    BILLING_CURRENCY      = os.environ.get("BILLING_CURRENCY", "gbp")

    SESSION_COOKIE_HTTPONLY  = True
    # Must be "Lax", not "Strict": the user returns from checkout.stripe.com
    # via a top-level GET, which carries a Lax cookie but not a Strict one.
    # Under Strict they would land on /billing?checkout=success logged out.
    SESSION_COOKIE_SAMESITE  = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    # CSRF is checked on every mutating request. Do not set this to False: that
    # switches CSRFProtect's check off entirely, not just loosens it. The
    # frontend fetches /api/csrf-token and sends it as X-CSRFToken.
    WTF_CSRF_CHECK_DEFAULT = True
    # The header the frontend already sends (api/client.js).
    WTF_CSRF_HEADERS = ["X-CSRFToken", "X-CSRF-Token"]
    # Tie the token's lifetime to the session rather than expiring it after an
    # hour: a token that dies while the tab is open turns into a mystery
    # failure on the next save, and the session cookie is already the thing
    # that bounds how long a client stays trusted.
    WTF_CSRF_TIME_LIMIT = None

    # Set when running behind a reverse proxy or tunnel (Cloudflare Tunnel,
    # ngrok, IIS/nginx). Without it every request appears to come from the
    # proxy's IP, so one user's failed logins would rate-limit everybody.
    TRUST_PROXY = _bool_env("TRUST_PROXY", False)

    # ── security headers ──────────────────────────────────────────────────
    # A strict policy is achievable here because the app loads nothing from
    # anywhere else: no CDN, no web fonts, no analytics, no embedded content.
    # 'unsafe-inline' is needed for style-src only — React sets inline styles
    # on elements, and the app uses style props in several places. There is no
    # inline <script>, so script-src stays strict, which is the half that
    # matters for XSS.
    CSP_POLICY = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "frame-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    # Off by default so a report-only rollout is possible without a code change.
    CSP_REPORT_ONLY = _bool_env("CSP_REPORT_ONLY", False)
    # 180 days. Not preloaded: preload is effectively irreversible, and that is
    # a decision to take deliberately once the domain is settled.
    HSTS_MAX_AGE = _int_env("HSTS_MAX_AGE", 15552000)


class DevelopmentConfig(Config):
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    # Secure cookies are only sent over HTTPS. That is the right default, but it
    # means a plain-HTTP LAN deployment silently drops the session cookie and
    # users appear logged out immediately after logging in. Serve over HTTPS
    # (a tunnel is the easy way) or set SESSION_COOKIE_SECURE=0 for LAN testing.
    SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", True)


config_map = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
}
