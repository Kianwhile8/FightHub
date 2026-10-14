# FightHub container image.
#
# Builds the React frontend, then bakes it into a Python image that serves both
# the API and the built SPA. Runs unchanged on Cloud Run, a VM, or locally —
# what differs between them is environment variables, not this file.
#
#   docker build -t fighthub .
#   docker run --rm -p 8080:8080 --env-file .env fighthub

# ── stage 1: build the frontend ──────────────────────────────────────────
FROM node:20-slim AS frontend

WORKDIR /build
# Copy manifests first so the dependency layer is cached across source edits.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


# ── stage 2: runtime ─────────────────────────────────────────────────────
FROM python:3.13-slim

# PYTHONUNBUFFERED keeps logs flowing to Cloud Logging in real time rather than
# sitting in a buffer until the process exits.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# psycopg2-binary ships its own libpq, so no apt packages are needed here.
COPY requirements ./requirements
RUN pip install --no-cache-dir -r requirements

COPY app/ ./app/
COPY migrations/ ./migrations/
COPY wsgi.py entrypoint.sh ./
COPY --from=frontend /build/dist ./frontend/dist

# Run as a non-root user. Cloud Run does not require it, but a container that
# only ever needs to read its own code has no business running as root.
RUN chmod +x entrypoint.sh \
 && useradd --create-home --uid 10001 fighthub \
 && chown -R fighthub:fighthub /srv
USER fighthub

# Cloud Run injects PORT and ignores EXPOSE; this is for local docker run.
ENV PORT=8080
EXPOSE 8080

CMD ["./entrypoint.sh"]
