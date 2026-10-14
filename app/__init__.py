"""Application factory.

`create_app()` builds the Flask app: loads config, wires up extensions,
attaches the auth and billing services, registers every blueprint, and adds
the security headers, error handlers and SPA catch-all route.
"""

import os
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.security import safe_join
from flask_wtf.csrf import generate_csrf, CSRFError
from dotenv import load_dotenv

from .validation import ValidationError

load_dotenv()


def create_app(config_name: str | None = None) -> Flask:
    """Build and return a configured Flask app.

    `config_name` is "development" or "production"; when omitted it is chosen
    from FLASK_DEBUG.
    """
    if config_name is None:
        config_name = "development" if os.environ.get("FLASK_DEBUG") == "1" else "production"

    root_dir     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frontend_dir = os.path.join(root_dir, "frontend", "dist")

    # No automatic static route: mounting it at "" registers `/<path:filename>`,
    # which shadows the SPA catch-all below and 404s deep links like
    # /fighters/kickboxing instead of serving index.html. The catch-all serves
    # the built frontend itself.
    app = Flask(__name__, static_folder=None)

    from .config import config_map
    app.config.from_object(config_map[config_name])

    # Behind a reverse proxy or tunnel, rewrite the remote address and scheme
    # from the X-Forwarded-* headers. Without this every request looks like it
    # came from the proxy, so the login rate limit would be shared by all users.
    if app.config.get("TRUST_PROXY"):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable is not set. See .env.example.")

    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        raise RuntimeError("DATABASE_URL environment variable is not set. See .env.example.")

    # A short SECRET_KEY is the whole of session security and CSRF signing, so
    # refuse to start production on one that could be brute-forced. Warn rather
    # than refuse in development, where a throwaway key is the point.
    if len(app.config["SECRET_KEY"]) < 32:
        message = (f"SECRET_KEY is only {len(app.config['SECRET_KEY'])} characters. "
                   "Use at least 32 — `python -c \"import secrets; "
                   "print(secrets.token_hex(32))\"`.")
        if config_name == "production":
            raise RuntimeError(message)
        app.logger.warning(message)

    # Extensions
    from .extensions import db, migrate, limiter, csrf
    db.init_app(app)
    migrate.init_app(app, db)
    limiter.init_app(app)
    csrf.init_app(app)

    # Import every model so Flask-Migrate can see them. A model that is never
    # imported is invisible to `flask db migrate` autogenerate, which then
    # writes a revision that drops its table. The names are unused on purpose.
    with app.app_context():
        from .models import User, Gym, Fighter, FighterRecord, PriorExperience  # noqa: F401
        from .models import FightHistory                                        # noqa: F401
        from .models import Venue, Event, EventBout, EventRegistration          # noqa: F401
        from .models import DemoRecord, DeletionRequest                         # noqa: F401
        from .models import Subscription, WebhookEvent                          # noqa: F401

    # Services live on the app object, one instance each, and are reached from
    # any request as `current_app.auth_db` and `current_app.billing_db`.
    from .services.auth_service import AuthService
    app.auth_db = AuthService()

    from .services.billing_service import BillingService
    app.billing_db = BillingService()

    # Register blueprints
    from .blueprints.auth       import auth_bp
    from .blueprints.fighters   import fighters_bp
    from .blueprints.gyms       import gyms_bp
    from .blueprints.events     import events_bp
    from .blueprints.event_crud import event_crud_bp
    from .blueprints.rankings   import rankings_bp
    from .blueprints.admin      import admin_bp
    from .blueprints.uploads    import uploads_bp
    from .blueprints.billing    import billing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(fighters_bp)
    app.register_blueprint(gyms_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(event_crud_bp)
    app.register_blueprint(rankings_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(billing_bp)

    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

    @app.after_request
    def security_headers(response):
        """Add security headers to every response.

        The Content-Security-Policy does most of the work: an injected <script>
        will not run even if one gets into the page, and `frame-ancestors
        'none'` stops the app being framed for clickjacking.
        """
        csp_header = ("Content-Security-Policy-Report-Only"
                      if app.config.get("CSP_REPORT_ONLY")
                      else "Content-Security-Policy")
        response.headers.setdefault(csp_header, app.config["CSP_POLICY"])
        # Stops a browser second-guessing a declared content type — the reason
        # an uploaded file with a .png extension cannot be talked into running
        # as script.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        # The app uses none of these browser features, so disable them all.
        #
        # `payment=()` does not affect billing: it only disables the in-page
        # Payment Request API. Stripe Checkout is a full-page redirect to
        # checkout.stripe.com, which this header does not govern.
        #
        # The headers that DO constrain billing are in CSP_POLICY (config.py):
        # `frame-src 'none'` rules out embedded Checkout, `script-src 'self'`
        # means js.stripe.com is never loaded, and `form-action 'self'` means
        # the redirect must be window.location.assign(), not a form POST.
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), camera=(), microphone=(), payment=(), usb=(), "
            "interest-cohort=()")
        # Only over HTTPS, and only in production: sending HSTS from a plain
        # HTTP dev server would pin localhost to HTTPS in the developer's
        # browser and be a nuisance to undo.
        if request.is_secure and app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault(
                "Strict-Transport-Security",
                f"max-age={app.config['HSTS_MAX_AGE']}; includeSubDomains")
        return response

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    @limiter.exempt   # static asset serving; one page load is many requests
    def index(path):
        """Serve the built frontend, falling back to index.html so client-side
        routes survive a refresh or a shared link."""
        if path.startswith("api/"):
            return jsonify({"error": "Not found."}), 404
        if path:
            # safe_join returns None for traversal attempts (../etc).
            candidate = safe_join(frontend_dir, path)
            if candidate and os.path.isfile(candidate):
                return send_from_directory(frontend_dir, path)
        return send_from_directory(frontend_dir, "index.html")

    @app.errorhandler(404)
    def handle_404(e):
        """API clients get JSON; anything else gets the SPA.

        /uploads/ is excluded from the SPA fallback: a missing image should be a
        404, not an HTML page returned with 200 that the browser then fails to
        decode as an image.
        """
        if request.path.startswith("/api/") or request.path.startswith("/uploads/"):
            return jsonify({"error": "Not found."}), 404
        return send_from_directory(frontend_dir, "index.html")

    @app.errorhandler(500)
    @app.errorhandler(Exception)
    def handle_unexpected(e):
        """Unhandled errors must still answer an API client in JSON.

        Flask's default 500 page is HTML, so any bug in an /api/ route reached
        the frontend as "Unexpected token '<', "<!doctype "... is not valid
        JSON" — a message that says nothing about what failed and sends you
        looking at the client instead of the server. The real error goes to the
        logs; the client gets something it can parse and display.
        """
        from werkzeug.exceptions import HTTPException
        # Let genuine HTTP errors (404, 403, 413 …) keep their own handling.
        if isinstance(e, HTTPException) and e.code != 500:
            return e
        app.logger.exception("unhandled error on %s %s", request.method, request.path)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Something went wrong handling that request. "
                                     "The error has been logged."}), 500
        return e

    @app.errorhandler(429)
    def handle_rate_limited(e):
        """Rate-limit refusals in JSON.

        flask-limiter's default response is an HTML page, which the frontend
        cannot parse — the user would see a JSON syntax error instead of being
        told to wait.
        """
        retry_after = getattr(e, "retry_after", None)
        body = {
            "error": "Too many attempts. Please wait a little and try again.",
            "detail": str(getattr(e, "description", "")) or None,
        }
        response = jsonify(body)
        response.status_code = 429
        if retry_after:
            response.headers["Retry-After"] = str(int(retry_after))
        return response

    @app.errorhandler(413)
    def handle_too_large(e):
        """An upload over MAX_CONTENT_LENGTH."""
        limit_mb = app.config.get("MAX_CONTENT_LENGTH", 0) // (1024 * 1024)
        return jsonify({"error": f"That file is too large. The limit is {limit_mb} MB."}), 413

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        """A missing or stale CSRF token, as JSON.

        419 rather than 400 because the frontend already special-cases it: it
        drops its cached token, fetches a fresh one and tells the user to
        refresh (see frontend/src/api/client.js).
        """
        return jsonify({
            "error": "Your session token has expired or is missing. "
                     "Please refresh the page and try again.",
            "csrf": True,
        }), 419

    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        """Input the caller can correct — always a 400, never a 500."""
        return jsonify({"error": str(e)}), 400

    @app.route("/api/csrf-token")
    @limiter.exempt   # fetched before the first mutating request of a session
    def csrf_token():
        """Give the SPA a CSRF token to send back in the X-CSRFToken header."""
        return jsonify({"token": generate_csrf()})

    @app.route("/api/health")
    @limiter.exempt   # polled by the platform's health check, not by users
    def health():
        """Liveness check. Always 200; `db` says whether Postgres answers."""
        try:
            db.session.execute(db.text("SELECT 1"))
            db_status = "ok"
        except Exception:
            db_status = "error"
        return jsonify({"status": "ok", "db": db_status})

    # Admin seeding is a deploy-time step, not a request-time one — see
    # `flask --app wsgi seed-admin`. serve.py runs it at startup.
    from .cli import register_cli
    register_cli(app)

    return app
