# FightHub — Security Audit

**Date:** 19 September 2026
**Scope:** the whole repository — Flask API, React frontend, Alembic migrations, container and deploy configuration.
**Method:** manual review of every route, model, service and template; targeted searches for hardcoded credentials, third-party resources and payment code; and functional tests of the fixes against a throwaway database.

This document records what was found, what was fixed in this pass, and what remains. Findings are rated by what an attacker gains, not by how hard they are to fix.

---

## Summary

| Severity | Found | Fixed now | Remaining |
|---|---|---|---|
| Critical | 1 | 1 | 0 |
| High | 4 | 4 | 0 |
| Medium | 8 | 5 | 3 |
| Low | 7 | 3 | 4 |

The single most serious finding was that **CSRF protection was configured but switched off**, so the token the frontend had been dutifully sending on every mutating request for months was never once checked. That is fixed.

Two items requested for this audit had nothing to act on, and both are good news:

- **No payment or fee code exists anywhere.** There are no hidden fees because there is no charging mechanism of any kind (see §5).
- **The frontend makes no external network request at all** — no CDN, no fonts, no analytics, no SDK (see §4).

---

## 1. Fixed in this pass

### 1.1 CSRF protection was disabled — *Critical*

`app/config.py` set `WTF_CSRF_CHECK_DEFAULT = False`. That does not merely relax the check: it short-circuits `CSRFProtect`'s `before_request` hook entirely, so no token was validated on any request, ever. No code called `csrf.protect()` either.

The frontend had been doing its part the whole time — fetching `/api/csrf-token` and attaching `X-CSRFToken` to every POST, PUT, PATCH and DELETE (`frontend/src/api/client.js`). It even carried error handling for a 419 response that could never arrive. The server discarded all of it.

**Impact.** Any site a signed-in user visited could submit requests to FightHub as them. `SESSION_COOKIE_SAMESITE = "Lax"` was the only thing standing in the way — it blocks cross-site POSTs from forms and scripts, which covers the common case, but it is one browser-side default doing the work of an application control, it does not cover every navigation-initiated request, and it silently stops protecting anything if the cookie policy is ever loosened.

**Fixed.** `WTF_CSRF_CHECK_DEFAULT = True`, with `WTF_CSRF_HEADERS` naming the header the client already sends and `WTF_CSRF_TIME_LIMIT = None` so a token lasts as long as its session rather than expiring mid-visit. `CSRFError` now returns JSON 419 instead of an HTML page. The client retries once with a fresh token before surfacing an error, so signing out and back in no longer needs a manual refresh.

Verified: `POST /api/auth/login` without a token returns 419; with one, it succeeds.

### 1.2 Unauthenticated access to every fighter's personal data — *High*

`GET /api/<sport>/rankings` and `GET /api/stats` carried no `@login_required`, while every other route in the application did. The rankings endpoint returned each fighter's full record — name, age, weight, gender, gym, county, win/loss history — to anyone who asked, no account needed.

The privacy masking on that route ran with `current_user()` returning `None`, so it only ever hid the records of users who had explicitly set "hide my record"; everyone else was fully exposed. For a platform whose privacy notice promises that nothing is visible without an account, this was the promise being broken.

**Fixed.** Both routes now require a session. Verified: anonymous requests return 401.

### 1.3 A duplicate route one line-swap away from being unauthenticated — *High*

`/api/<sport>/fighters/<id>/matches` was registered twice: in `fighters.py` with `@login_required`, and again in `rankings.py` without it. Flask matched the protected one only because `fighters_bp` happened to be registered first in the app factory. Reordering two adjacent `register_blueprint` calls — a change no reviewer would think twice about — would have silently removed authentication from that endpoint.

**Fixed.** The unauthenticated duplicate is deleted, with a comment where it was explaining why.

### 1.4 Sign-in rate limiting was too loose to matter — *High*

Only two routes were limited at all, both at 10 per minute — 14,400 password guesses per day against one account, from one address. Everything else in the application, including the expensive rankings endpoint and the 5 MB avatar upload, was completely unthrottled (`default_limits=[]`).

**Fixed.**

| Route | Limit | Notes |
|---|---|---|
| `POST /api/auth/login` | **5 per 15 min**, twice | One bucket per IP, one per email address |
| `POST /api/auth/register` | 5 per hour | Was 10/min, which allowed hundreds of accounts a day |
| `POST /api/auth/change-password` | 5 per 15 min | Also verifies a password |
| `POST /api/auth/deletion-request` | 10 per hour | Bounds the password check without obstructing a rights request |
| `POST /api/upload/avatar` | 10 per hour | Each request writes up to 5 MB to billed storage |
| everything else | 400/hour, 60/min | Global default; static serving and health are exempt |

Two details worth keeping: the login limits are keyed on **both** the caller's address and the submitted email, so a distributed attack cannot grind one account by rotating IPs; and successful sign-ins do not consume the budget (`deduct_when`), so getting your password right on the fifth attempt does not then lock you out.

`429` responses are now JSON with a `Retry-After` header, instead of an HTML page the frontend could not parse.

**Caveat — these limits are only real with shared storage.** The default `memory://` backend keeps counters inside one process, so the effective limit is 5 × (number of processes). Waitress serves from a single process, so it is genuinely equivalent there; Gunicorn with `WEB_CONCURRENCY > 1` and Cloud Run are not. On Cloud Run the failure mode is perverse: it adds instances under load, so an attacker raises their own allowance by attacking harder. `check-deploy` now **fails** when it detects either of those two cases and stays quiet for a single process.

### 1.5 Sign-in leaked which email addresses hold accounts — *Medium*

`"No account found with that email address."` versus `"Incorrect password."` turned the login form into a membership oracle: enter a name, learn whether that person competes. For a platform holding minors' records and physical attributes, that is a meaningful disclosure on its own, and it is the first step in credential stuffing.

**Fixed.** One message for both. A dummy hash is verified when the account does not exist, so the response time no longer gives back what the message withholds.

### 1.6 No security headers at all — *Medium*

No CSP, no HSTS, no `X-Frame-Options`, no `X-Content-Type-Options`, no `Referrer-Policy`.

**Fixed** via `after_request`. Because the application loads nothing from anywhere else, a genuinely strict policy was achievable:

```
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
img-src 'self' data: blob:; font-src 'self'; connect-src 'self';
object-src 'none'; frame-src 'none'; frame-ancestors 'none';
base-uri 'self'; form-action 'self'
```

`'unsafe-inline'` is needed for `style-src` only, because React sets inline styles on elements. `script-src` stays strict, which is the half that stops XSS. The built `index.html` contains no inline script, so nothing needed loosening. `CSP_REPORT_ONLY=1` allows a report-only rollout.

HSTS (180 days) is sent only over HTTPS in production, and the domain is deliberately **not** preloaded — preload is effectively irreversible.

### 1.7 Unbounded input on every field — *Medium*

Nothing in the application capped a string length. The sharpest edge was the password field: every submitted password is run through scrypt, and scrypt on a one-megabyte input is a CPU-denial-of-service primitive available to anonymous callers at the sign-in endpoint.

Free text was also stored with whatever control characters it arrived with — NUL bytes, bidirectional overrides, zero-width joiners — which then travelled into every listing, export and log line containing that name.

**Fixed.** New `app/validation.py` with `clean_str` (length cap, control and invisible character stripping, NFKC normalisation), `clean_email`, `clean_password` (8–128), `clean_int`, `clean_float` (rejects NaN and infinity, which pass every bounds check and then poison any sort), `clean_enum`, `clean_date` and `clean_text_block`. `ValidationError` maps to a JSON 400 globally.

`helpers.clean_str` now delegates to it rather than keeping a second, more lenient copy.

Applied at the service layer — the chokepoint every path goes through, including the CLI seeder — rather than per-route:

| Field | Bound |
|---|---|
| Email | ≤254, validated shape, NFKC-normalised, lowercased |
| Password | 8–128 characters, never trimmed |
| Fighter name | ≤100, required, control characters stripped |
| Weight | 20–400 kg (the old `weight > 0` CHECK accepted 0.5 kg) |
| Description | ≤200 words **and** ≤2000 characters |
| County | must be one of the 48 in the list |
| Gym name / location | ≤100 / ≤200 |

**Note on HTML:** free text is stored exactly as written and escaped where it is rendered. React does that by default, and the CSP backs it up. Escaping on the way in instead corrupts legitimate input — a gym called "Smith & Son" becoming "Smith &amp; Son" in the database — and creates a false impression that the stored value is safe everywhere.

### 1.8 County was a menu, not a constraint — *Medium*

The county list existed only in `frontend/src/constants/counties.js`, so the field accepted any string posted directly and stored it verbatim. Since county is also a filter value, a typo produced a county nobody could ever match on.

**Fixed.** `app/constants.py` holds the server-side list; both the fighter and gym paths validate against it.

### 1.9 The seeded administrator password — *Medium*

`seed_admin()` runs unconditionally at startup (`serve.py`) and on container boot when `SEED_ADMIN=1`, and only checked that the password was at least 8 characters. The value in the working-tree `.env` was `nimda321` — "admin" reversed with three digits. That is the credential guarding the account that can read every user's email address and erase any account.

**Fixed.** The seeder now refuses to create the account on a password under 12 characters or one matching a small blocklist of well-known weak values, and prints why. It refuses rather than warns, because a warning printed during a container start is a warning nobody reads.

**Action still required by the operator:** rotate `ADMIN_PASSWORD`, and see §3.1.

### 1.10 A short `SECRET_KEY` would be accepted silently — *Medium*

`SECRET_KEY` signs the session cookie and the CSRF token; forging it forges both. The app checked only that it was set.

**Fixed.** Production refuses to start on a key shorter than 32 characters; development logs a warning.

### 1.11 The database password was written into Alembic's logs — *Low*

`migrations/env.py` rendered the connection URL with `hide_password=False` into Alembic's config, which is echoed into its logging output — so every migration run wrote the production database password into the deploy log.

**Fixed.** The config now carries a masked URL. Online migrations connect through `get_engine()` and are unaffected; offline mode (`--sql`), which is the one caller that genuinely needs credentials, asks for them explicitly.

### 1.12 Dependencies were unpinned — *Low*

Every line in `requirements` used `>=` with no lockfile and no hashes. Two builds of the same commit could ship different dependency trees, and a compromised upstream release would arrive on the next `docker build` with nothing in the repository having changed.

**Fixed.** All twelve direct dependencies pinned to the versions this work was tested against.

### 1.13 A compiled `.pyc` was committed to git — *Low*

`__pycache__/fighter_database.cpython-314.pyc` was tracked despite `__pycache__/` being in `.gitignore` — it predated the rule. Bytecode of a dead module, but it is a stale artefact in the source tree and it was being deployed.

**Fixed.** Removed from the index.

### 1.14 Raw exception text returned to clients — *Low*

`GET /api/<sport>/rankings` caught every exception and returned `str(e)` to the caller — table names, column names, and occasionally fragments of a connection string.

**Fixed.** Logged server-side; the caller gets a generic message.

---

## 2. Remaining findings

Nothing here is exploitable in the way §1.1 was, but each should be scheduled.

### 2.1 Uploads are validated by file extension only — *Medium*

`app/blueprints/uploads.py` checks that the filename ends in `.png`, `.jpg`, `.jpeg`, `.webp` or `.gif`. There is no magic-byte inspection, no re-encoding and no dimension check. A file whose contents are anything at all is stored and later served as an image.

*Mitigated by:* stored filenames are replaced with a UUID, so the attacker does not control the path; `X-Content-Type-Options: nosniff` (added in this pass) stops a browser reinterpreting the declared type; and the CSP blocks script execution regardless. The residual risks are decompression bombs and image-parser exploits in whatever eventually reads the file.

*Recommended:* verify magic bytes, then re-encode through Pillow and store only the re-encoded output. Cap pixel dimensions as well as bytes — a 40,000 × 40,000 PNG is small on disk and enormous in memory. This adds a Pillow dependency, which is why it was left out of this pass.

### 2.2 `/uploads/<filename>` requires no authentication — *Medium*

Any profile photograph or event banner can be fetched by anyone who knows the URL. Filenames are UUIDs, so they are not enumerable, but this is security by obscurity and a URL shared once is public forever.

This sits awkwardly beside the privacy notice, which tells users photographs are "served through the platform to signed-in users" and that consent can be withdrawn by deleting the image. Deleting it does remove the object, so the promise holds in substance — but the access control described is not actually enforced.

*Recommended:* require a session on `/uploads/`, or accept the current behaviour explicitly and amend the notice to match. The notice should not describe a control that does not exist.

### 2.3 `GCS_PUBLIC_URLS` makes uploaded images world-readable — *Medium*

When set, the app redirects to `blob.public_url` and the bucket's objects must be publicly readable — bypassing the application entirely, and with it any access control §2.2 might add later. Honestly documented in the code, and off by default.

*Recommended:* leave it off. If the bandwidth saving is ever needed, use signed URLs with a short expiry instead.

### 2.4 Email verification is scaffolded but not implemented — *Low*

`User.email_verified`, `email_verified_at`, the `REQUIRE_VERIFIED_EMAIL` config flag and migration `e7b21c904f6a` all exist. Nothing reads or writes any of them, and there is no send-or-confirm route. Registration grants a full session immediately, so accounts can be created on addresses the registrant does not control.

*Blocked on:* a mail provider. `MAIL_PROVIDER`, `MAIL_API_KEY` and `MAIL_FROM` are configured for but unused.

### 2.5 No password reset — *Low*

A forgotten password means an administrator edits the database. Same blocker as §2.4.

### 2.6 A blanket `Exception` handler — *Low*

`@app.errorhandler(Exception)` in the app factory catches everything. It correctly re-raises non-500 `HTTPException`s, so the new 419, 429 and 413 handlers work, but it means any unhandled exception in a new route returns a generic 500 rather than being noticed.

*Recommended:* keep it as a backstop, but add error reporting so these surface rather than disappearing into logs. Note that an error-reporting SDK would be the first external dependency in the frontend (§4) and would need a CSP amendment.

### 2.7 A second, unmaintained copy of the application is still in the tree — *Low, but see note*

`app_v1.py` is a 759-line pre-blueprint monolith that re-implements every route, including register, login and the admin endpoints, with its own CSRF configuration and no connection to the current auth service. Alongside it: root-level `auth.py`, `fighter_database.py`, `matchmaker.py`, `seed_demo.py`, `app/services/fighter_db.py`, `app/services/auth_db.py` and `frontend/index_v1.html`.

None are imported by the live application and none are copied into the container (`.dockerignore` excludes them), so this is not remotely exploitable. The risk is to maintenance: every fix in this document was applied to the live code only, so the repository now contains a complete authentication surface that is knowingly insecure, and anyone who runs `python app_v1.py` gets it.

*Recommended:* delete all of it. Git has the history. **Not done in this pass — awaiting confirmation, as it is destructive and outside the requested scope.**

### 2.8 Legacy SQLite databases on disk — *Low*

`data/auth.db`, `boxing.db`, `kickboxing.db` and `mma.db` contain historical password hashes. Git-ignored and excluded from the image, but present in the working tree and included in any directory-level backup.

*Recommended:* delete or move them off the machine.

### 2.9 "Hide my record" does less than the name suggests — *Informational*

It withholds results and removes the fighter from matchmaking, but name, age, weight, gym and county stay visible. This is deliberate, and §2 of the privacy notice explains it in plain terms. Noted here only so it is not mistaken for a bug later.

---

## 3. Secrets

**No secret is hardcoded in any tracked file.** Every one is read from the environment; the app refuses to boot without `SECRET_KEY` or `DATABASE_URL`; and `git log --all -- .env` confirms `.env` has never been committed.

Searches run across all Python, JavaScript, JSX, HTML, YAML, Dockerfile, shell and Markdown files for: `api[_-]?key`, `secret`, `token\s*=`, `password\s*=`, `Bearer`, `sk-`, `AIza`, `pk_live`, `-----BEGIN`, and base64-shaped strings over 40 characters. Every match was a placeholder, a permission-allowlist entry, or prose.

### 3.1 Action required: rotate the working-tree `.env`

The untracked `.env` on the development machine holds live values, including a `SECRET_KEY`, a `DATABASE_URL` with an embedded password, and the weak `ADMIN_PASSWORD` described in §1.9.

Recommended, in order:

1. **Rotate `SECRET_KEY`.** `python -c "import secrets; print(secrets.token_hex(32))"`. This invalidates every existing session, which is the intended effect.
2. **Rotate `ADMIN_PASSWORD`,** and change the password on the existing admin account — the seeder only guards *creation*, so an account already seeded with the weak value keeps it.
3. **Rotate the database password** and update it in Secret Manager.
4. Confirm `FLASK_DEBUG=1` is only ever set locally. In production it selects `DevelopmentConfig`, which sets `SESSION_COOKIE_SECURE = False`.

Production secrets are already held in Google Secret Manager and injected via `--set-secrets` (`DEPLOY.md`), which is the right arrangement.

---

## 4. Third-party SDK audit

**The frontend makes no external network request of any kind.** Verified by searching every `https?://` in `frontend/src`, `frontend/index.html`, `frontend/dist/index.html` and `frontend/index_v1.html`: no matches.

- No CDN. Every dependency is bundled by Vite and self-hosted.
- No web fonts — `index.css` uses a system font stack, with no `@font-face` or `@import`.
- No analytics, tag manager, session recorder or error reporter.
- No icon library; icons are hand-written inline SVG.
- No embedded content, no iframes, no social widgets.

**npm dependencies** (all bundled, none loaded at runtime from elsewhere): react, react-dom, react-router-dom, @tanstack/react-query, zustand, sonner, @dnd-kit/{core,sortable,utilities}. Dev only: vite, @vitejs/plugin-react.

**Python third-party service SDK:** `google-cloud-storage` alone, imported lazily and only when `STORAGE_BACKEND=gcs`.

**Data leaving the platform:** none, other than to Google Cloud as the hosting processor. No user data is transmitted to any third party.

This is an unusually clean position and worth defending deliberately. It is what makes the strict CSP in §1.6 possible. **Adding any consent-management platform, analytics tool or error reporter would break it** and would require a CSP amendment — and, in the case of analytics, would make the currently-decorative consent categories load-bearing.

*Recommended:* add `npm audit` and `pip-audit` to CI so known vulnerabilities in the pinned versions surface without anyone having to remember to look.

---

## 5. Hidden fees

**There are none, because there is no charging mechanism at all.**

Searches for `stripe`, `paypal`, `checkout`, `payment`, `subscription`, `billing`, `invoice`, `price`, `fee`, `charge`, `premium`, `upgrade`, `plan` and `tier` across the whole repository returned three categories of match, all benign:

- GCP **billing account** setup in `DEPLOY.md` — infrastructure cost, paid by the operator, nothing to do with users.
- "billing" in `FightCardArranger.jsx` in its combat-sports sense — top billing, main event, co-main.
- The word "checkout" in a comment in `storage.py`.

There is no payment model, no card handling, no pricing page, no feature gated behind money, and no code path that could charge anyone.

Since "remove any hidden fees" cannot be satisfied by deleting code that does not exist, it has been addressed in the document that governs the relationship instead: **§2 of the Terms of Service** now states plainly that the platform is free, that there is no paid tier, subscription, per-event fee or commission, that no payment details are collected, and that no charge could be introduced for an existing account without its holder agreeing first.

---

## 6. Injection and access control

**SQL injection:** not reachable. Everything goes through the SQLAlchemy ORM with bound parameters. The one raw statement (`app/cli.py`, the migration advisory lock) also uses bound parameters.

**XSS:** no `dangerouslySetInnerHTML`, no `eval`, no `innerHTML` assignment anywhere in the frontend. React escapes by default, and the CSP now blocks inline and external script regardless.

**Path traversal:** the SPA catch-all and `/uploads/` both use `safe_join`, and `/uploads/` additionally rejects any filename containing a slash.

**Access control:** reviewed route by route. After the fixes in §1.2 and §1.3, every route except `/api/health`, `/api/csrf-token`, `/uploads/` (§2.2) and the static frontend requires a session. Role checks use the shared `roles_required` decorator consistently; gym-scoped operations additionally verify ownership via `_coach_owns_fighter`; admins cannot delete their own account, and cannot request their own erasure through the new deletion queue.

**Session handling:** signed cookies, `HttpOnly`, `SameSite=Lax`, `Secure` in production, 8-hour lifetime, cleared on sign-out.

**Password storage:** `werkzeug.security` with scrypt defaults, per-password salt. Not reversible, and now bounded in length (§1.7).

---

## 7. What to do next

In order of value:

1. **Rotate the three secrets in §3.1.** Nothing else in this document matters as much as the weak admin password.
2. **Set `RATELIMIT_STORAGE_URL` to Redis before deploying to Cloud Run or adding Gunicorn workers.** The limits in §1.4 are per-process without it; `check-deploy` fails in both of those cases. The current single-process Waitress setup does not need it.
3. **Fill in the controller contact address.** Both legal documents still carry the placeholder `privacy@fighthub.example`, which makes the erasure and complaint procedures unusable by anyone outside the project.
4. Decide §2.2 — authenticate `/uploads/`, or amend the privacy notice to describe what actually happens.
5. Delete the legacy application (§2.7), once confirmed.
6. Harden uploads (§2.1) when Pillow can be added.
7. Build email verification and password reset (§2.4, §2.5) when a mail provider is chosen.
