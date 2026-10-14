# Deploying FightHub to Cloud Run

The app ships as one container serving both the API and the built React frontend.
The same image runs locally, on a VM, or on Cloud Run — only environment
variables differ.

You get an HTTPS URL (`https://fighthub-xxxxx.<region>.run.app`) as soon as the
first deploy finishes. A custom domain is a later, optional step.

> gcloud flags move between releases. If a command is rejected, check
> `gcloud <command> --help` rather than assuming the setup is wrong.

> **On Windows, go to [Appendix A](#appendix-a-windows-powershell) first.** The
> commands below are POSIX `sh`. PowerShell does not understand `\` as a line
> continuation, so pasting them there sends gcloud a literal backslash as its
> argument — which is what produces
> `Not found or permission denied for service(s): \`.

---

## 0. Before you start

```sh
gcloud auth login

# 'FightHub' is a display name. Commands take the project *ID*, which is
# globally unique and usually has a suffix. List it — and confirm you are
# logged in as the account that owns it:
gcloud projects list

# Nothing listed? The project lives under a different Google account. Either
# `gcloud auth login` as that one, or create it under this one:
#   gcloud projects create fighthub-prod-1 --name=FightHub

gcloud config set project YOUR_PROJECT_ID
gcloud config set run/region europe-west2      # pick one near your users

# Cloud SQL and Cloud Run both require billing on the project. A brand new
# project has none, and the failure shows up several steps later.
gcloud billing accounts list
gcloud billing projects link YOUR_PROJECT_ID --billing-account=XXXXXX-XXXXXX-XXXXXX

gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com
```

You do **not** need Docker installed. `gcloud run deploy --source .` builds the
image with Cloud Build using the `Dockerfile` in this repo.

Set some shell variables so the commands below can be pasted as-is:

```sh
PROJECT=$(gcloud config get-value project)
REGION=europe-west2
INSTANCE=fighthub-db
BUCKET=${PROJECT}-fighthub-uploads
SA=fighthub-run@${PROJECT}.iam.gserviceaccount.com
```

---

## 1. Postgres (Cloud SQL)

```sh
gcloud sql instances create $INSTANCE \
  --database-version=POSTGRES_16 \
  --edition=ENTERPRISE \
  --tier=db-f1-micro \
  --region=$REGION \
  --storage-size=10GB \
  --backup-start-time=03:00

gcloud sql databases create fighthub --instance=$INSTANCE
gcloud sql users create fighthub --instance=$INSTANCE --password='PICK_A_STRONG_ONE'
```

`--edition=ENTERPRISE` is required. gcloud now defaults Postgres 16 instances to
Enterprise Plus, which rejects every shared-core tier with
`Invalid Tier (db-f1-micro) for (ENTERPRISE_PLUS) Edition`.

**This instance bills continuously**, roughly £8-9/month at `db-f1-micro`. Unlike
Cloud Run it does not scale to zero, so it is the one line item that costs money
while the app sits idle. `gcloud sql instances delete fighthub-db` removes it.

`--backup-start-time` is what turns on automated daily backups. Don't skip it —
it is the single cheapest insurance on this list.

The instance connection name (`PROJECT:REGION:INSTANCE`) is needed below:

```sh
CONN=$(gcloud sql instances describe $INSTANCE --format='value(connectionName)')
```

### Connection limits — read this one

`db-f1-micro` allows roughly **25 concurrent connections**. Each Cloud Run
instance opens its own SQLAlchemy pool, so your ceiling is:

```
max-instances × WEB_CONCURRENCY × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
```

The repo defaults (pool 10, overflow 5) with 4 instances would try to open 60
connections and fail in a way that looks like random 500s under load. The
settings in step 5 keep it to `2 × 1 × (5 + 2) = 14`. If you raise
`--max-instances`, lower the pool to match or move to a bigger tier.

---

## 2. Bucket for uploads

Cloud Run's filesystem is per-instance and is wiped on every deploy, so avatars
and photos must live in object storage.

```sh
gcloud storage buckets create gs://$BUCKET --location=$REGION --uniform-bucket-level-access
```

Keep the bucket private. The app streams images through itself by default, which
needs no public access and no URL signing. Revisit that only when egress cost
starts mattering — see `GCS_PUBLIC_URLS` in `.env.example`.

---

## 3. Service account

```sh
gcloud iam service-accounts create fighthub-run --display-name="FightHub Cloud Run"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:${SA}" --role="roles/cloudsql.client"

gcloud storage buckets add-iam-policy-binding gs://$BUCKET \
  --member="serviceAccount:${SA}" --role="roles/storage.objectAdmin"
```

---

## 4. Secrets

Never bake `.env` into the image — `.dockerignore` already excludes it.

```sh
python -c "import secrets; print(secrets.token_hex(32))" \
  | gcloud secrets create fighthub-secret-key --data-file=-

# Note the URL-encoding warning below before running this.
printf 'postgresql+psycopg2://fighthub:PICK_A_STRONG_ONE@/fighthub?host=/cloudsql/%s' "$CONN" \
  | gcloud secrets create fighthub-database-url --data-file=-

printf 'YOUR_ADMIN_PASSWORD' | gcloud secrets create fighthub-admin-password --data-file=-

# Billing — only needed if you are taking subscriptions. See section 8, which
# explains why these cannot be created until after the first deploy.
printf 'sk_live_...'  | gcloud secrets create fighthub-stripe-secret-key --data-file=-
printf 'whsec_...'    | gcloud secrets create fighthub-stripe-webhook-secret --data-file=-

for S in fighthub-secret-key fighthub-database-url fighthub-admin-password \
         fighthub-stripe-secret-key fighthub-stripe-webhook-secret; do
  gcloud secrets add-iam-policy-binding $S \
    --member="serviceAccount:${SA}" --role="roles/secretmanager.secretAccessor"
done
```

The Stripe **price** ids (`price_…`) are deliberately *not* secrets. They are
public identifiers that appear in checkout URLs, so they go in `--set-env-vars`
and the Secret Manager surface stays as small as possible.

**The database password must be URL-encoded inside `DATABASE_URL`.** A password
containing `@`, `/`, `:`, `#` or `?` will silently produce a malformed URL and a
connection error that points nowhere near the real cause. Either stick to
alphanumerics or percent-encode it.

Rotating `fighthub-secret-key` later invalidates every session and logs all
users out. That is the correct behaviour, just don't do it casually.

---

## 5. Deploy

```sh
gcloud run deploy fighthub \
  --source . \
  --region $REGION \
  --service-account $SA \
  --add-cloudsql-instances $CONN \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 2 \
  --cpu 1 --memory 512Mi \
  --set-env-vars "FLASK_DEBUG=0,TRUST_PROXY=1,SESSION_COOKIE_SECURE=1,STORAGE_BACKEND=gcs,GCS_BUCKET=${BUCKET},RUN_MIGRATIONS=1,SEED_ADMIN=1,WEB_CONCURRENCY=1,WEB_THREADS=8,DB_POOL_SIZE=5,DB_MAX_OVERFLOW=2,ADMIN_EMAIL=you@example.com" \
  --set-secrets "SECRET_KEY=fighthub-secret-key:latest,DATABASE_URL=fighthub-database-url:latest,ADMIN_PASSWORD=fighthub-admin-password:latest"
```

**Leave billing off for this first deploy.** `BILLING_ENABLED` defaults to `0`,
so the command above ships the paywall inert — every feature is free and
`/api/billing/*` refuses. That is deliberate: the Stripe webhook URL contains the
Cloud Run URL, which does not exist until this deploy has finished. Section 8
turns it on.

### Cloud Build permissions — new projects only

The first `--source` deploy in a brand new project fails with:

```
could not resolve source: ... <number>-compute@developer.gserviceaccount.com
does not have storage.objects.get access to the Google Cloud Storage object
```

Since 2024 Google no longer grants the default compute service account the
Editor role on new projects, and that account is what Cloud Build runs as. It
needs the builder role once:

```sh
PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT   --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"   --role="roles/cloudbuild.builds.builder"
```

Nothing is wrong with the Dockerfile when this happens — the build never starts.

What the important flags do:

| Flag / var | Why |
|---|---|
| `TRUST_PROXY=1` | Cloud Run terminates TLS upstream. Without this every request looks like it came from the load balancer, so per-user rate limiting becomes global. |
| `SESSION_COOKIE_SECURE=1` | Cloud Run is HTTPS-only, so this is safe and correct here. |
| `RUN_MIGRATIONS=1` | Applies pending migrations at boot under a Postgres advisory lock, so simultaneous instances can't race into a half-applied schema. |
| `SEED_ADMIN=1` | Creates the admin from `ADMIN_EMAIL`/`ADMIN_PASSWORD`. Safe to leave on — it is idempotent — but you can drop it after the first deploy. |
| `--min-instances 0` | Scales to zero, so an idle app costs nothing but the first request after idle waits a few seconds for a cold start. Set to `1` when that becomes annoying; it costs roughly a always-on small instance. |

Once it returns a URL, set it so email links (later) and any absolute URLs are
correct:

```sh
URL=$(gcloud run services describe fighthub --region $REGION --format='value(status.url)')
gcloud run services update fighthub --region $REGION \
  --update-env-vars "PUBLIC_BASE_URL=${URL}"
```

---

## 6. Verify

```sh
curl -s "$URL/api/health"          # {"status":"ok","db":"ok"}
```

Then in a browser: load `$URL`, log in as the admin, upload a profile picture,
and **redeploy** — the picture must survive. If it doesn't, `STORAGE_BACKEND` is
not set to `gcs` and uploads are still going to the container's disk.

For a fuller check:

```sh
gcloud run services proxy fighthub --region $REGION      # then hit localhost
gcloud run services logs read fighthub --region $REGION --limit 50
```

The app also has a self-check that reports storage backend, rate limiter, proxy
trust and admin presence:

```sh
flask --app wsgi check-deploy
```

---

## 7. Custom domain (optional)

The `run.app` URL is real HTTPS and fine to launch on. When you want your own:

```sh
gcloud beta run domain-mappings create --service fighthub --domain fighthub.example.com --region $REGION
```

Add the DNS records it prints. Domain mapping is not available in every region;
if yours is excluded, put a Global External Application Load Balancer in front
instead. Remember to update `PUBLIC_BASE_URL` afterwards.

---

## 8. Stripe subscriptions

Pricing is **£20/year** for coaches and promoters (the `pro` plan) and
**£10/year** for fighters, both annual and in GBP. Every new account gets a
7-day free trial; accounts that existed before the paywall migration are
grandfathered with indefinite complimentary access.

### The ordering trap

The webhook endpoint URL contains the Cloud Run URL, and that does not exist
until the service has been deployed once. So this cannot be done in one pass:

1. **Deploy with `BILLING_ENABLED=0`** — section 5 above. The app runs, the
   paywall is inert, nobody can be charged.
2. **Set `PUBLIC_BASE_URL`** to the URL that deploy printed (or your custom
   domain, if you did section 7 — do that first if you intend to).
3. **Create the two prices** in the Stripe dashboard → Product catalogue. Each
   must be **recurring, yearly, GBP**: £10 "FightHub Fighter" and £20 "FightHub
   Pro". Copy both `price_…` ids.
4. **Add the webhook endpoint**: Developers → Webhooks → Add endpoint, pointing
   at `$URL/api/billing/webhook`, subscribed to exactly these events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`
   - `charge.refunded`
   - `charge.dispute.created`
5. **Put the signing secret in Secret Manager** (section 4), along with your
   live secret key.
6. **Redeploy with billing on:**

```sh
gcloud run deploy fighthub --source . --region $REGION \
  --update-env-vars "BILLING_ENABLED=1,TRIAL_DAYS=7,PUBLIC_BASE_URL=https://your-url,STRIPE_PRICE_FIGHTER=price_xxx,STRIPE_PRICE_PRO=price_yyy,PRICE_FIGHTER_PENCE=1000,PRICE_PRO_PENCE=2000" \
  --update-secrets "STRIPE_SECRET_KEY=fighthub-stripe-secret-key:latest,STRIPE_WEBHOOK_SECRET=fighthub-stripe-webhook-secret:latest"
```

7. **Verify:**

```sh
gcloud run services proxy fighthub --region $REGION   # then in another shell
# or run it inside the container:
flask --app wsgi check-deploy
```

`check-deploy` retrieves both prices from Stripe and fails if the amount,
interval or currency disagrees with what the app displays. It also **fails on a
`sk_test_` key when it detects Cloud Run** — a live deploy in test mode behaves
completely normally and silently never charges anybody, which is the one failure
here that could cost a month of revenue without producing a single error.

### Testing without real money

Use a test-mode key and the Stripe CLI:

```sh
stripe login
stripe listen --forward-to localhost:5000/api/billing/webhook
```

That prints a `whsec_…`. **It is not the same value as a dashboard endpoint's
signing secret** — mixing the two produces a 400 on every delivery and is the
most common local-setup confusion. Test cards:

| Card | Behaviour |
|---|---|
| `4242 4242 4242 4242` | succeeds |
| `4000 0000 0000 9995` | declines |
| `4000 0000 0000 0341` | attaches, then fails the first charge (exercises `past_due`) |
| `4000 0027 6000 3184` | forces 3-D Secure |

`stripe trigger customer.subscription.deleted` fires a handler without clicking
through Checkout, and `stripe events resend <evt_id>` tests idempotency — the
second delivery must leave `billing_events` with exactly one row.

Two CLI helpers make the local loop quick:

```sh
flask --app wsgi billing-status you@example.com         # print the entitlement
flask --app wsgi billing-expire-trial you@example.com   # FLASK_DEBUG=1 only
```

### Comps and refunds

An administrator can grant or withdraw complimentary access from the admin panel
(**Comp** / **Revoke** on each user row). Revoke deliberately **refuses** when the
account's access comes from a live Stripe subscription: clearing it locally
without cancelling at Stripe would keep taking their money while denying them the
product. Cancel in the Stripe dashboard instead.

Refunds and disputes are recorded but do **not** automatically revoke access — a
dispute over £20 is a conversation plus the Revoke button, and auto-revoking
would punish a customer whose bank flagged a card.

### Before you take real money

Two things are still not done:

- **`CONTROLLER.contact` in `frontend/src/legal/terms.js` is still the
  placeholder `privacy@fighthub.example`.** It is the address a data-subject
  request, an erasure request or an ICO complaint gets sent to — a placeholder
  there means those currently go nowhere. Replace it with a real inbox you
  monitor (it does not need to be @fighthub.co.uk) before anyone outside the
  project relies on this. `CONTROLLER.name` and a trading address are also
  legally required on invoices once real money moves — decide the VAT position
  too (whether £20 is inclusive, and whether you are VAT-registered).
- **Nothing in the SPA prompts for re-acceptance when `TERMS_VERSION` /
  `PRIVACY_VERSION` change.** `GET /api/auth/legal` already reports when a
  signed-in user's stored version is older than current — see `app/legal.py` —
  but no UI reads that response yet. Wire it up before relying on version bumps
  (like the one on 2026-10-03, below) to actually get anyone to re-agree.

Already done, as of 2026-10-03:

- The Terms of Service (`§2 What it costs`) now describe the real trial +
  paid-subscription model instead of claiming the platform is always free.
- The Privacy Notice discloses Stripe as a processor (§4) and lists the
  billing data it returns (§1), alongside the existing Google Cloud entry.
- Both documents carry a note (`DOMAIN_NOTE` in `terms.js`) that the service
  currently runs from the `run.app` address while `fighthub.co.uk` — or
  whatever domain ends up registered — is pending. Remove that note, and bump
  both version constants again, once the move to section 7's custom domain
  actually happens: that is exactly the kind of change clause 8 of the Terms
  promises to flag.

---

## Redeploying

```sh
gcloud run deploy fighthub --source . --region $REGION
```

Existing env vars and secrets are preserved. Migrations apply automatically on
boot. To roll back, Cloud Run keeps revisions:

```sh
gcloud run revisions list --service fighthub --region $REGION
gcloud run services update-traffic fighthub --region $REGION --to-revisions REVISION=100
```

**Rolling back code does not roll back the database.** Every migration in this
repo has a working `downgrade()`, but you have to run it deliberately.

---

## Known limits at this size

These are fine with no customers and worth revisiting before you have many.

- **Rate limiting is per-instance.** `flask-limiter` defaults to in-memory
  storage, so with `--max-instances 2` a limit of 10/min is really 20/min. Point
  `RATELIMIT_STORAGE_URL` at Memorystore Redis when it needs to be exact.
- **Images stream through the app.** Simple and private, but every view costs
  Cloud Run CPU and egress. Public bucket + CDN is the fix when traffic justifies it.
- **`--min-instances 0` means cold starts.** A few seconds on the first request
  after an idle period, mostly Python import and pool setup.
- **Cold-start migrations add to that.** Negligible now; if the migration set
  ever grows slow, move `RUN_MIGRATIONS` to a separate Cloud Run Job in your
  deploy pipeline instead of running it at boot.
- **Migrations cannot be replayed on SQLite.** `f1bc7ea5cac9` adds a CHECK
  constraint referencing `age` inside a `batch_alter_table`, which SQLite
  rejects with `no such column: age`. The chain applies cleanly on Postgres, so
  this only bites if you try to build a fresh local database with
  `flask db upgrade` against SQLite.
- **Stripe webhook delivery is at-least-once and can lag.** A renewal Stripe has
  taken but not yet announced is covered by `BILLING_GRACE_DAYS` (default 2), and
  a delivery that failed to apply shows up in the admin panel under "Stripe
  webhook events". `past_due` keeps access on purpose while Stripe retries.
- **The free trial can be obtained again** by deleting an account and
  registering the same email. Accepted: it costs £10 of nothing, and deletions
  go through an admin-reviewed queue.
- **A gym with three coaches needs three subscriptions.** Billing is per user
  because a `Gym` has exactly one `coach_id` and there is no seat table.
  `subscriptions.gym_id` exists, unused, so gym-level seats can be added without
  migrating live billing data.

---

## Appendix A: Windows PowerShell

Everything above is POSIX `sh`. Five constructs in it behave differently in
PowerShell, and the failures are all quiet or misleading:

| `sh` | PowerShell | What goes wrong otherwise |
|---|---|---|
| `\` at end of line | backtick `` ` `` — with **nothing** after it, not even a space | PowerShell passes the literal `\` as the argument. This is the `services: \` in the error. |
| `VAR=value` | `$VAR = "value"` | `REGION=europe-west2` is parsed as a command name and fails |
| `for S in a b; do … done` | `foreach ($s in "a","b") { … }` | parse error |
| `printf … \| gcloud --data-file=-` | write a temp file first (below) | PowerShell appends CRLF and may add a UTF-8 BOM, so the secret's value ends up as `<value>\r\n` and the DB URL silently fails to parse |
| `curl` | `curl.exe` | `curl` is an alias for `Invoke-WebRequest`, which takes different flags |

Also: `gcloud` fails to start under Git Bash on this machine — the shim picks up
the broken system Python 3.14. PowerShell is fine, because `gcloud.cmd` uses the
SDK's bundled Python. If you do want Git Bash, set this first:

```sh
export CLOUDSDK_PYTHON="D:/googlecloudCLI/google-cloud-sdk/platform/bundledpython/python.exe"
```

### A.0 Project, billing, APIs

Use a named configuration so this doesn't clobber the settings of any other
project you work on. `gcloud config configurations activate <name>` switches
back.

```powershell
gcloud auth login          # must be the account that owns the FightHub project

# 'FightHub' is a display name; every command needs the project ID.
gcloud projects list

# Not listed? It belongs to another Google account. Log in as that one, or
# create the project here (the ID must be globally unique):
#   gcloud projects create fighthub-prod-1 --name=FightHub

gcloud config configurations create fighthub
gcloud config set project YOUR_PROJECT_ID
gcloud config set run/region europe-west2

gcloud billing accounts list
gcloud billing projects link YOUR_PROJECT_ID --billing-account=XXXXXX-XXXXXX-XXXXXX

# One line on purpose - no continuations to get wrong.
gcloud services enable run.googleapis.com sqladmin.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com
```

### A.1 Variables

```powershell
$PROJECT  = "YOUR_PROJECT_ID"
$REGION   = "europe-west2"
$INSTANCE = "fighthub-db"
$BUCKET   = "${PROJECT}-fighthub-uploads"
$SA       = "fighthub-run@${PROJECT}.iam.gserviceaccount.com"
```

These live in the current window only. Open a new terminal and you must set them
again, or the later commands quietly pass empty strings.

### A.2 Cloud SQL

```powershell
gcloud sql instances create $INSTANCE `
  --database-version=POSTGRES_16 `
  --edition=ENTERPRISE `
  --tier=db-f1-micro `
  --region=$REGION `
  --storage-size=10GB `
  --backup-start-time=03:00

gcloud sql databases create fighthub --instance=$INSTANCE

$DBPASS = "PickAStrongAlphanumericOne"     # see the URL-encoding note in step 4
gcloud sql users create fighthub --instance=$INSTANCE --password=$DBPASS

$CONN = gcloud sql instances describe $INSTANCE '--format=value(connectionName)'
```

Single-quote `'--format=value(connectionName)'` as shown. Unquoted, PowerShell
reads the `(` as the start of a subexpression.

### A.3 Bucket and service account

```powershell
gcloud storage buckets create "gs://$BUCKET" --location=$REGION --uniform-bucket-level-access

gcloud iam service-accounts create fighthub-run --display-name="FightHub Cloud Run"

gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA" --role="roles/cloudsql.client"

gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" --member="serviceAccount:$SA" --role="roles/storage.objectAdmin"
```

### A.4 Secrets

Do **not** pipe into `--data-file=-` from PowerShell. Write a temp file with an
explicit encoding instead — `WriteAllText` adds no BOM and no trailing newline:

```powershell
function Set-GcpSecret($Name, $Value) {
  $f = [IO.Path]::GetTempFileName()
  [IO.File]::WriteAllText($f, $Value, (New-Object System.Text.UTF8Encoding $false))
  gcloud secrets create $Name --data-file=$f
  Remove-Item $f -Force
}

Set-GcpSecret fighthub-secret-key     (python -c "import secrets; print(secrets.token_hex(32))")
Set-GcpSecret fighthub-database-url   "postgresql+psycopg2://fighthub:${DBPASS}@/fighthub?host=/cloudsql/${CONN}"
Set-GcpSecret fighthub-admin-password "YOUR_ADMIN_PASSWORD"

# Billing — only if you are taking subscriptions. The webhook secret cannot be
# created until the service has a URL, so see A.7.
Set-GcpSecret fighthub-stripe-secret-key     "sk_live_..."
Set-GcpSecret fighthub-stripe-webhook-secret "whsec_..."

foreach ($s in "fighthub-secret-key","fighthub-database-url","fighthub-admin-password",
               "fighthub-stripe-secret-key","fighthub-stripe-webhook-secret") {
  gcloud secrets add-iam-policy-binding $s --member="serviceAccount:$SA" --role="roles/secretmanager.secretAccessor"
}
```

To check a secret came out clean — the length should be exactly what you expect,
with no stray `\r\n`:

```powershell
gcloud secrets versions access latest --secret=fighthub-database-url | Format-Hex | Select-Object -Last 2
```

### A.5 Deploy

```powershell
gcloud run deploy fighthub `
  --source . `
  --region $REGION `
  --service-account $SA `
  --add-cloudsql-instances $CONN `
  --allow-unauthenticated `
  --min-instances 0 --max-instances 2 `
  --cpu 1 --memory 512Mi `
  --set-env-vars "FLASK_DEBUG=0,TRUST_PROXY=1,SESSION_COOKIE_SECURE=1,STORAGE_BACKEND=gcs,GCS_BUCKET=$BUCKET,RUN_MIGRATIONS=1,SEED_ADMIN=1,WEB_CONCURRENCY=1,WEB_THREADS=8,DB_POOL_SIZE=5,DB_MAX_OVERFLOW=2,ADMIN_EMAIL=you@example.com" `
  --set-secrets "SECRET_KEY=fighthub-secret-key:latest,DATABASE_URL=fighthub-database-url:latest,ADMIN_PASSWORD=fighthub-admin-password:latest"

$URL = gcloud run services describe fighthub --region $REGION '--format=value(status.url)'
gcloud run services update fighthub --region $REGION --update-env-vars "PUBLIC_BASE_URL=$URL"
```

### A.6 Verify

```powershell
curl.exe -s "$URL/api/health"
gcloud run services logs read fighthub --region $REGION --limit 50
```

### A.7 Turn billing on (second pass)

A.5 deploys with `BILLING_ENABLED` unset, i.e. off. Create the two annual GBP
prices and the webhook endpoint in the Stripe dashboard first — the endpoint URL
is `$URL/api/billing/webhook`, which only exists once A.5 has run — then:

```powershell
gcloud run deploy fighthub --source . --region $REGION `
  --update-env-vars "BILLING_ENABLED=1,TRIAL_DAYS=7,STRIPE_PRICE_FIGHTER=price_xxx,STRIPE_PRICE_PRO=price_yyy,PRICE_FIGHTER_PENCE=1000,PRICE_PRO_PENCE=2000" `
  --update-secrets "STRIPE_SECRET_KEY=fighthub-stripe-secret-key:latest,STRIPE_WEBHOOK_SECRET=fighthub-stripe-webhook-secret:latest"
```

`PUBLIC_BASE_URL` was already set at the end of A.5, and billing requires it.
See section 8 for the full sequence, the test cards, and what still has to be
written before real money can be taken.
