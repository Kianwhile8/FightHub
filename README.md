# FightHub

Fighter database, matchmaking and event management for kickboxing, MMA, boxing and Muay Thai.

Flask + PostgreSQL API with a React (Vite) single-page frontend.

## Requirements

- **Python 3.13** (3.10+ works; 3.14 is currently avoided — see Troubleshooting)
- **Node.js 20+** and npm
- **PostgreSQL 14+** running locally or reachable via `DATABASE_URL`

## First-time setup

```powershell
# 1. Create and activate the virtual environment
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install Python dependencies
pip install -r requirements

# 3. Configure environment
copy .env.example .env
# then edit .env — at minimum set SECRET_KEY, DATABASE_URL, ADMIN_EMAIL, ADMIN_PASSWORD
# generate a SECRET_KEY with:
#   python -c "import secrets; print(secrets.token_hex(32))"

# 4. Create the database schema
flask --app wsgi db upgrade

# 5. Create the admin account (reads ADMIN_EMAIL / ADMIN_PASSWORD)
flask --app wsgi seed-admin

# 6. Build the frontend
npm --prefix frontend install
npm --prefix frontend run build
```

## Running

### Development (auto-reload, two processes)

```powershell
# Terminal 1 — API on :5000
$env:FLASK_DEBUG=1; python wsgi.py

# Terminal 2 — Vite dev server on :5173, proxies /api to :5000
npm --prefix frontend run dev
```

Open <http://localhost:5173>.

### Production / multi-user (single process, serves everything)

The Flask development server handles one request at a time, so it cannot serve
multiple users concurrently. Use Waitress instead — it runs a pool of worker
threads in one process and serves the built frontend from `frontend/dist`.

```powershell
npm --prefix frontend run build   # whenever the frontend changed
python serve.py
```

Open <http://localhost:5000>.

Verify configuration at any time with:

```powershell
flask --app wsgi check-deploy
```

## Letting other people in

`serve.py` binds to `127.0.0.1` (this machine only) by default.

**On your LAN** — set `HOST=0.0.0.0` and `SESSION_COOKIE_SECURE=0` in `.env`,
then allow the port through Windows Firewall. Others visit `http://<your-ip>:5000`.
Plain HTTP means passwords and session cookies travel unencrypted, so this is for
trusted-network testing only.

**Over the internet** — put an HTTPS tunnel in front of it rather than forwarding
ports. Keep `SESSION_COOKIE_SECURE=1` and set `TRUST_PROXY=1` so per-user rate
limiting sees real client IPs instead of the tunnel's.

> **Why `SESSION_COOKIE_SECURE` matters:** with it on, browsers only send the
> session cookie over HTTPS. Serve over plain HTTP with it on and login returns
> `200` but the user is immediately logged out again.

## Configuration

All settings live in `.env` — see [.env.example](.env.example) for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | *(required)* | Signs session cookies. Changing it logs everyone out. |
| `DATABASE_URL` | *(required)* | PostgreSQL connection string. |
| `HOST` / `PORT` | `127.0.0.1` / `5000` | Bind address for `serve.py`. |
| `WAITRESS_THREADS` | `8` | Concurrent requests served. Keep `<= DB_POOL_SIZE`. |
| `DB_POOL_SIZE` | `10` | Connection pool, shared by all threads. |
| `SESSION_COOKIE_SECURE` | `1` | Require HTTPS for session cookies. |
| `TRUST_PROXY` | `0` | Honour `X-Forwarded-*`. Set to `1` behind a tunnel/proxy. |
| `FLASK_DEBUG` | `0` | `1` selects the development config. Never `1` in production. |

## Database migrations

```powershell
flask --app wsgi db migrate -m "describe the change"
flask --app wsgi db upgrade
```

## Troubleshooting

**`ModuleNotFoundError: No module named 'html.entities'`, or `logging` has no
attribute `Logger`** — the Python 3.14 install under
`%LOCALAPPDATA%\Python\pythoncore-3.14-64` is missing standard-library files.
Rebuild the virtual environment against Python 3.13:

```powershell
Rename-Item .venv .venv.broken
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements
```

**Login succeeds but the user is instantly logged out** — you are serving over
plain HTTP with `SESSION_COOKIE_SECURE=1`. Either serve over HTTPS or set it to `0`.

**`FATAL: too many connections`** — `WAITRESS_THREADS` or `DB_POOL_SIZE` is too
high for your PostgreSQL `max_connections`.
