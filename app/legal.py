"""Versioned legal documents.

The terms are stored as a *version string*, not a body of text, because what
has to be provable under UK GDPR Art. 7(1) is which wording a user agreed to
and when — not the wording itself, which lives in the frontend and in git.

Bump the relevant version whenever the substance of that document changes.
Existing users then have a stored version older than this constant, which is
what `GET /api/auth/legal` reports so the UI can prompt them again. Cosmetic
edits (typos, formatting) should NOT bump it — re-prompting every user for a
comma is consent fatigue, and it trains people to click through without
reading.

Each constant has a counterpart in the frontend, which holds the wording
itself: TERMS_VERSION in frontend/src/legal/terms.js, PRIVACY_VERSION and
COOKIE_POLICY_VERSION in frontend/src/legal/privacy.js. Change them together.
"""

# ISO date of the version, which doubles as the "last updated" shown to users.
#
# 2026-10-03: terms rewritten to describe the real trial + paid-subscription
# model (Stripe) instead of the "always free" wording written before billing
# existed — a live contradiction between what users agreed to and what the
# product actually does. Also added the temporary-domain disclosure
# (DOMAIN_NOTE in frontend/src/legal/terms.js). Both are changes of substance,
# hence the bump of both versions below.
TERMS_VERSION = "2026-10-03"

# The privacy notice is versioned separately from the terms because the two are
# now separate documents with separate reasons to change: the terms are a
# contract, the notice is the Art. 13 disclosure. A change to how data is
# handled should not force re-agreement to unchanged contractual terms, and a
# change to the contract should not restate the notice.
#
# 2026-10-03: disclosed Stripe as a payment processor (section 4) and added
# the billing-data row to the data-collected table (section 1) — billing did
# not exist, and was not disclosed, when this notice last changed.
PRIVACY_VERSION = "2026-10-03"

# The cookie policy is part of the privacy notice, but the consent banner has
# to know when to ask again on its own — a stored choice is only valid for the
# policy it was given against. Bump this when the cookies themselves change,
# not when the wording describing them does.
COOKIE_POLICY_VERSION = "2026-09-19"

# Minimum age to hold an account. UK GDPR Art. 8 sets the age of consent for
# information society services at 13, but this platform publishes fight records
# and physical attributes, so 16 is the floor here and under-18s need the
# consent of a parent, guardian or coach.
MINIMUM_AGE = 16
