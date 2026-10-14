#!/bin/sh
# Container entrypoint. Optionally migrates and seeds, then serves.
#
# Both startup steps are opt-in so the same image can run as a plain web server,
# as a migration job, or as a one-shot admin seed.
set -eu

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    echo "[entrypoint] applying database migrations"
    # deploy-migrate takes a Postgres advisory lock, so several instances
    # starting at once cannot race each other into a half-applied schema.
    python -m flask --app wsgi deploy-migrate
fi

if [ "${SEED_ADMIN:-0}" = "1" ]; then
    echo "[entrypoint] seeding admin account"
    python -m flask --app wsgi seed-admin
fi

# One worker with several threads matches the SQLAlchemy pool, which is
# per-process: raising WEB_CONCURRENCY multiplies connections against Cloud
# SQL's limit, so raise DB_POOL_SIZE with it or you will exhaust the instance.
exec gunicorn wsgi:app \
    --bind ":${PORT:-8080}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --threads "${WEB_THREADS:-8}" \
    --timeout "${WEB_TIMEOUT:-60}" \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile - \
    --forwarded-allow-ips '*'
