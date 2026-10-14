import os
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

db      = SQLAlchemy()
migrate = Migrate()

# A ceiling on every route, so a new endpoint is throttled the day it is added
# rather than the day somebody notices it is not. Generous enough that ordinary
# use never meets it — a busy page load is a handful of requests — and low
# enough to make scraping the fighter list tedious.
#
# Sign-in and the other sensitive routes set their own, tighter limits on top;
# the strictest applicable limit is the one that applies.
DEFAULT_LIMITS = ["400 per hour", "60 per minute"]

limiter = Limiter(
    get_remote_address,
    default_limits=DEFAULT_LIMITS,
    storage_uri=os.environ.get("RATELIMIT_STORAGE_URL", "memory://"),
    # Count against the limit before the route runs, not after. The default
    # defers the deduction to teardown, which means a burst arriving together
    # is all admitted before any of it is counted.
    strategy="fixed-window",
    headers_enabled=True,     # X-RateLimit-* so a client can back off politely
)

csrf = CSRFProtect()
