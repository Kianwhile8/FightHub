"""Flask CLI commands.

Run with the app factory discovered from wsgi.py:

    flask --app wsgi seed-admin
    flask --app wsgi routes

Commands, by group:
  setup      seed-admin, deploy-migrate, check-deploy
  demo data  seed-demo, demo-runs, clear-demo, seed-multidivision,
             matchmaker-report
  billing    billing-status, billing-expire-trial
"""

import json
import os

import click
from flask import current_app

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _user_by_email(email: str) -> dict:
    """Look up an account by email for the billing commands, or exit.

    Queries the model directly because AuthService has no get_by_email and
    these commands are its only would-be callers.
    """
    from .models.user import User
    user = User.query.filter_by(email=(email or "").strip().lower()).first()
    if not user:
        raise SystemExit(f"no account with email {email}")
    return user.to_dict()


def _on_cloud_run() -> bool:
    """Cloud Run sets K_SERVICE in every container."""
    return bool(os.environ.get("K_SERVICE"))


def register_cli(app) -> None:
    """Attach every command below to `app.cli`."""
    @app.cli.command("seed-admin")
    def seed_admin_command():
        """Create the admin account from ADMIN_EMAIL / ADMIN_PASSWORD."""
        current_app.auth_db.seed_admin()

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Add demonstration gyms, fighters, fights and events.

        Everything created is recorded so `clear-demo` can remove exactly it.
        Safe to run on a database that already holds real data.
        """
        from .services.demo_seed import DemoSeeder
        result = DemoSeeder().run()
        click.echo(f"seeded run {result['run_id']}")
        for entity, n in sorted(result["counts"].items()):
            click.echo(f"  {entity:12s} {n}")
        click.echo("remove with: flask --app wsgi clear-demo "
                   f"--run {result['run_id']}")

    @app.cli.command("demo-runs")
    def demo_runs_command():
        """List the demo seed runs currently in the database."""
        from .services.demo_seed import list_runs
        runs = list_runs()
        if not runs:
            click.echo("no demo data present")
            return
        for r in runs:
            total = sum(r["counts"].values())
            click.echo(f"{r['run_id']}  {r['created_at']:%Y-%m-%d %H:%M}  {total} rows")
            click.echo("   " + ", ".join(f"{k}={v}" for k, v in sorted(r["counts"].items())))

    @app.cli.command("clear-demo")
    @click.option("--run", "run_id", default=None,
                  help="Remove only this run. Omit to remove all demo data.")
    @click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
    def clear_demo_command(run_id, yes):
        """Delete seeded demo data. Real records are never touched."""
        from .services.demo_seed import clear_demo, list_runs
        runs = list_runs()
        if not runs:
            click.echo("no demo data present")
            return
        target = f"run {run_id}" if run_id else f"all {len(runs)} run(s)"
        if not yes:
            click.confirm(f"Delete demo data for {target}?", abort=True)
        result = clear_demo(run_id)
        for entity, n in sorted(result["removed"].items()):
            click.echo(f"  removed {entity:12s} {n}")
        click.echo("done")

    @app.cli.command("seed-multidivision")
    def seed_multidivision_command():
        """Add the cross-division matchmaking fixture.

        A small controlled cast of fighters who hold profiles in more than one
        discipline, built to show what the matchmaker does with transferred
        experience. Tracked as a demo run, so `clear-demo --run <id>` removes
        exactly it.
        """
        from .services.multidivision_seed import MultiDivisionSeeder
        result = MultiDivisionSeeder().run()
        click.echo(f"seeded run {result['run_id']}")
        for entity, n in sorted(result["counts"].items()):
            click.echo(f"  {entity:12s} {n}")
        click.echo("report with: flask --app wsgi matchmaker-report")
        click.echo("remove with: flask --app wsgi clear-demo "
                   f"--run {result['run_id']}")

    @app.cli.command("matchmaker-report")
    @click.option("--out", "out_path", default=None,
                  help="Write the report to this file as well as the terminal.")
    def matchmaker_report_command(out_path):
        """Show how matchmaking responds to the cross-division fixture."""
        from .services.multidivision_report import report
        lines = []

        def emit(line=""):
            lines.append(str(line))
            click.echo(line)

        report(out=emit)
        if out_path:
            with open(out_path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            click.echo(f"written to {out_path}")

    @app.cli.command("billing-status")
    @click.argument("email")
    def billing_status_command(email):
        """Print the computed entitlement envelope for one account.

        This is what /api/auth/me sends the browser, so it is the quickest way
        to see why someone is or is not being asked to pay.
        """
        user = _user_by_email(email)
        ent = current_app.billing_db.entitlement(user)
        click.echo(f"{user['email']}  role={user['role']}")
        click.echo(json.dumps(ent, indent=2))
        sub = current_app.billing_db.get_for_user(user["id"])
        click.echo("\nrow: " + (json.dumps(sub.to_dict(), indent=2) if sub
                                else "none"))

    @app.cli.command("billing-expire-trial")
    @click.argument("email")
    def billing_expire_trial_command(email):
        """Backdate an account's trial so the paywall applies immediately.

        A testing shortcut, and refused outside development: on a production
        database this would cut a real user off mid-trial.
        """
        is_development = (app.debug
                          or app.config.get("ENV") == "development"
                          or os.environ.get("FLASK_DEBUG") == "1")
        if not is_development:
            raise SystemExit(
                "refusing outside development — set FLASK_DEBUG=1 if this is "
                "really a development database")
        from datetime import datetime, timedelta
        from .extensions import db
        from .models.subscription import Subscription
        user = _user_by_email(email)
        sub = Subscription.query.filter_by(user_id=user["id"]).first()
        if not sub:
            raise SystemExit("that account has no subscription row")
        sub.status = "trialing"
        sub.trial_ends_at = datetime.utcnow() - timedelta(days=1)
        # A comp would outrank the expired trial and the account would stay
        # entitled, which is not what anyone running this command wants.
        sub.comped_until = None
        sub.comp_reason = None
        db.session.commit()
        click.echo(f"{email}: trial backdated to {sub.trial_ends_at.isoformat()} "
                   "— the account is now read-only")

    @app.cli.command("deploy-migrate")
    def deploy_migrate_command():
        """Apply pending migrations, safe to call from every starting instance.

        Cloud Run can start several containers at once, and two Alembic runs
        racing each other on the same database is how you get a half-applied
        schema. A Postgres advisory lock serialises them: the first caller
        migrates, the rest wait and then find nothing to do.
        """
        from .extensions import db
        from flask_migrate import upgrade

        LOCK_ID = 4917355001   # arbitrary but stable — must match across instances

        if db.engine.dialect.name != "postgresql":
            upgrade()
            click.echo("migrations applied (no lock — not Postgres)")
            return

        conn = db.engine.connect()
        try:
            conn.exec_driver_sql("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
            click.echo("advisory lock acquired; applying migrations")
            upgrade()
            click.echo("migrations applied")
        finally:
            conn.exec_driver_sql("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))
            conn.close()

    @app.cli.command("check-deploy")
    def check_deploy_command():
        """Verify the app is configured to serve real users.

        Collects `notes` (fine) and `problems` (must fix) from each check,
        prints them, and exits non-zero if there are any problems.
        """
        from .extensions import db

        problems, notes = [], []

        try:
            db.session.execute(db.text("SELECT 1"))
            notes.append("database: reachable")
        except Exception as exc:
            problems.append(f"database unreachable: {exc}")

        if app.config.get("SESSION_COOKIE_SECURE"):
            notes.append("session cookie: Secure (HTTPS required)")
        else:
            notes.append("session cookie: NOT Secure (plain HTTP ok, LAN testing only)")

        if app.config.get("TRUST_PROXY"):
            notes.append("proxy headers: trusted (X-Forwarded-For honoured)")
        else:
            notes.append("proxy headers: not trusted (set TRUST_PROXY=1 behind a tunnel)")

        from .models.user import User
        if not User.query.filter_by(role="admin").first():
            problems.append("no admin account exists — run: flask --app wsgi seed-admin")
        else:
            notes.append("admin account: present")

        backend = app.config.get("STORAGE_BACKEND", "local")
        if backend == "local":
            notes.append("uploads: local disk "
                         "(NOT safe on Cloud Run — set STORAGE_BACKEND=gcs)")
        else:
            try:
                from .services.storage import get_storage
                notes.append(f"uploads: {get_storage().describe()}")
            except Exception as exc:
                problems.append(f"uploads backend misconfigured: {exc}")

        _check_rate_limiter(app, problems, notes)

        if not app.config.get("PUBLIC_BASE_URL"):
            notes.append("PUBLIC_BASE_URL: unset "
                         "(needed before confirmation emails can build links, "
                         "and required once BILLING_ENABLED=1)")

        _check_billing(app, problems, notes)

        dist = os.path.join(_PROJECT_ROOT, "frontend", "dist", "index.html")
        if os.path.exists(dist):
            notes.append("frontend build: present")
        else:
            problems.append("frontend/dist missing — run: npm --prefix frontend run build")

        for n in notes:
            click.echo(f"  ok   {n}")
        for p in problems:
            click.echo(click.style(f"  FAIL {p}", fg="red"))
        if problems:
            raise SystemExit(1)
        click.echo(click.style("\nReady to serve.", fg="green"))


# ── check-deploy helpers ──────────────────────────────────────────────────
# Each appends to `problems` (fails the check) or `notes` (informational).

def _check_rate_limiter(app, problems: list, notes: list) -> None:
    """Flag an in-memory rate limiter where there is more than one process.

    The memory backend keeps counters per process, so "5 sign-in attempts"
    really means 5 per process. Waitress is a single process (its threads share
    the counters), so that is fine locally. Gunicorn with WEB_CONCURRENCY > 1,
    or Cloud Run scaling out, multiplies the limit.
    """
    if not app.config.get("RATELIMIT_STORAGE_URL", "memory://").startswith("memory"):
        notes.append("rate limiter: shared backend")
        return

    from .config import _int_env
    workers = _int_env("WEB_CONCURRENCY", 1)
    if workers > 1 or _on_cloud_run():
        why = (f"WEB_CONCURRENCY={workers}" if workers > 1
               else "running on Cloud Run, which scales to several instances")
        problems.append(
            f"rate limiter: in-memory but {why}, so each process keeps "
            "its own counters and the sign-in limit is multiplied — set "
            "RATELIMIT_STORAGE_URL to a Redis URL")
    else:
        notes.append("rate limiter: in-memory (valid for a single "
                     "process; needs Redis before adding workers or "
                     "deploying to Cloud Run)")


def _check_billing(app, problems: list, notes: list) -> None:
    """Check the Stripe configuration end to end.

    Every mistake caught here is silent at runtime: a test key takes no money,
    a product id instead of a price id fails at checkout, and a missing webhook
    secret means payments are taken but never applied to the account.
    """
    if not app.config.get("BILLING_ENABLED"):
        notes.append("billing: disabled (BILLING_ENABLED=0 — everything is "
                     "free and /api/billing/* refuses)")
        return

    on_cloud_run = _on_cloud_run()
    secret_key   = app.config.get("STRIPE_SECRET_KEY")
    webhook_sec  = app.config.get("STRIPE_WEBHOOK_SECRET")

    # Secret key: present, and live mode when deployed.
    if not secret_key:
        problems.append("STRIPE_SECRET_KEY is not set but billing is enabled")
    elif secret_key.startswith("sk_test_") and on_cloud_run:
        problems.append(
            "Stripe is in TEST mode (sk_test_…) on a Cloud Run deploy — "
            "no real payment will ever be taken")
    else:
        mode = "test" if secret_key.startswith("sk_test_") else "live"
        notes.append(f"Stripe key: present ({mode} mode)")

    if not webhook_sec:
        problems.append(
            "STRIPE_WEBHOOK_SECRET is not set — payments would be taken "
            "and never applied to an account")
    else:
        notes.append("Stripe webhook secret: present")

    # Checkout sends the user back to PUBLIC_BASE_URL after paying.
    base = app.config.get("PUBLIC_BASE_URL")
    if not base:
        problems.append(
            "PUBLIC_BASE_URL is required when billing is enabled — it is "
            "what Checkout returns the user to after paying")
    elif not base.startswith("https://") and on_cloud_run:
        problems.append(f"PUBLIC_BASE_URL is not https:// ({base})")

    # Price ids: well-formed, and matching what the UI displays.
    expected = {
        "STRIPE_PRICE_FIGHTER": app.config.get("PRICE_FIGHTER_PENCE"),
        "STRIPE_PRICE_PRO":     app.config.get("PRICE_PRO_PENCE"),
    }
    currency = (app.config.get("BILLING_CURRENCY") or "gbp").lower()
    for key, pence in expected.items():
        price_id = app.config.get(key)
        if not price_id:
            problems.append(f"{key} is not set but billing is enabled")
            continue
        if not price_id.startswith("price_"):
            problems.append(
                f"{key}={price_id} is not a price id — a 'prod_…' "
                "product id here fails at checkout")
            continue
        if secret_key:
            _check_stripe_price(key, price_id, pence, currency, secret_key,
                                problems, notes)

    # Every account should have a subscription row. One without means
    # registration failed to create it.
    try:
        from .models.subscription import Subscription
        from .models.user import User
        orphans = (User.query
                   .outerjoin(Subscription, Subscription.user_id == User.id)
                   .filter(Subscription.id.is_(None))
                   .count())
        if orphans:
            problems.append(f"{orphans} account(s) have no subscription row")
        else:
            notes.append("subscriptions: every account has a row")
    except Exception as exc:
        problems.append(f"could not count subscription rows: {exc} "
                        "(has the migration been applied?)")


def _check_stripe_price(key, price_id, pence, currency, secret_key,
                        problems: list, notes: list) -> None:
    """Fetch one price from Stripe and compare it with what the UI displays.

    Proves the key, mode and id agree, and that Stripe will charge what the
    app shows. A network failure is only a note: it says nothing about
    whether the configuration is right.
    """
    try:
        import stripe
        stripe.api_key = secret_key
        # to_dict() because `.get` on a StripeObject raises AttributeError
        # instead of returning None.
        price = stripe.Price.retrieve(price_id).to_dict()
    except ImportError:
        problems.append("the stripe package is not installed but "
                        "billing is enabled")
        return
    except Exception as exc:
        notes.append(f"{key}: could not be verified against Stripe "
                     f"({type(exc).__name__}) — check manually")
        return

    bad = []
    if price.get("type") != "recurring":
        bad.append("not a recurring price")
    recurring = price.get("recurring") or {}
    if recurring.get("interval") != "year":
        bad.append(f"interval is {recurring.get('interval')}, not year")
    if (price.get("currency") or "").lower() != currency:
        bad.append(f"currency is {price.get('currency')}, not {currency}")
    if price.get("unit_amount") != pence:
        bad.append(f"Stripe charges {price.get('unit_amount')}p but "
                   f"the app displays {pence}p")
    if bad:
        problems.append(f"{key} ({price_id}): " + "; ".join(bad))
    else:
        notes.append(f"{key}: {pence}p/{currency}/year, matches Stripe")
