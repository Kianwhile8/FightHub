"""Production server for Windows (Waitress).

Gunicorn is POSIX-only, so Waitress is the production server here. It runs a
single process with a pool of worker threads, which means many users are served
concurrently while the rate limiter and connection pool stay process-local.

Usage:
    python serve.py

Environment (all optional, see .env.example):
    HOST              bind address   (default 127.0.0.1; use 0.0.0.0 for LAN)
    PORT              port           (default 5000)
    WAITRESS_THREADS  worker threads (default 8)
"""

import os
from dotenv import load_dotenv

load_dotenv()

from waitress import serve                # noqa: E402
from app import create_app                # noqa: E402

app = create_app()


def main() -> None:
    host    = os.environ.get("HOST", "127.0.0.1")
    port    = int(os.environ.get("PORT", "5000"))
    threads = int(os.environ.get("WAITRESS_THREADS", "8"))

    pool = app.config["SQLALCHEMY_ENGINE_OPTIONS"]["pool_size"]
    if threads > pool:
        print(f"[WARN] WAITRESS_THREADS={threads} exceeds DB_POOL_SIZE={pool}; "
              f"requests may queue waiting for a connection.")

    # Single process, single thread, before any request is served — no race.
    with app.app_context():
        app.auth_db.seed_admin()

    if not app.config.get("SESSION_COOKIE_SECURE"):
        print("[WARN] SESSION_COOKIE_SECURE is off — sessions will travel over "
              "plain HTTP. Fine for LAN testing, not for real users.")

    print(f"[FightHub] Serving on http://{host}:{port} with {threads} threads.")
    print("[FightHub] Press Ctrl+C to stop.")
    serve(app, host=host, port=port, threads=threads, ident="FightHub")


if __name__ == "__main__":
    main()
