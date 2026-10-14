"""Input cleaning and bounds for anything that arrives from a client.

The rules here are deliberately boring: trim it, cap it, check it is the type
and shape it claims to be, and reject it plainly when it is not. Three things
this module exists to stop, none of them exotic:

* Unbounded text. Nothing in the app capped a string length, so any field would
  accept a megabyte. The password field is the sharp end of that — every
  submitted password is run through scrypt, and scrypt on a 1 MB input is a
  CPU-denial-of-service primitive handed to anonymous callers.
* Control characters and invisible formatting. A NUL byte, a bidi override or a
  zero-width joiner in a fighter's name is never legitimate input, and it
  travels into every list, every export and every log line that name appears
  in.
* Silent type coercion. `float(request.args.get(...))` raising ValueError inside
  a route produced a 500 and an HTML error page the frontend could not parse.

HTML is *not* stripped or escaped here. Free text is stored exactly as written
and escaped at the point it is rendered — React does that by default, and the
Content-Security-Policy backs it up. Escaping on the way in instead corrupts
legitimate input (a gym called "Smith & Son" becoming "Smith &amp; Son" in the
database) and gives a false sense that the stored value is safe in contexts
where it is not.
"""

import re
import unicodedata
from datetime import date

# Characters no free-text field should ever contain. C0/C1 controls except tab,
# newline and carriage return; the zero-width and bidi-override range; and the
# BOM, which arrives on pasted input from Windows editors surprisingly often.
_CONTROL_RE = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f​-‏‪-‮⁦-⁩﻿]"
)

# Deliberately permissive. Full RFC 5322 validation is famously not worth
# attempting, and every stricter pattern rejects addresses that genuinely work.
# This catches typos and obvious junk; deliverability is proved by sending mail,
# not by a regular expression.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")

# RFC 5321: 64-character local part, 255-character domain, 254 in practice.
MAX_EMAIL_LEN = 254

# scrypt cost is paid per attempt by the server, so the ceiling is a denial-of-
# service control, not a security limit on the password itself. 128 is far
# beyond any real passphrase.
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128


class ValidationError(ValueError):
    """Raised for input a client could correct. Routes turn it into a 400."""


def scrub(value: str) -> str:
    """Strip control and invisible characters, and normalise the result.

    NFKC folds visually identical but distinct codepoints together — full-width
    Latin, ligatures, and the several Unicode spaces that are not U+0020 — so
    two names that look the same compare the same.
    """
    return _CONTROL_RE.sub("", unicodedata.normalize("NFKC", value))


def clean_str(value, default=None, max_len: int = None, field: str = "value"):
    """Trim a value from a JSON body, tolerating None.

    `data.get("description", "")` looks safe but is not: when the client sends
    an explicit null the key *is* present, so the default never applies and the
    call returns None. `.strip()` on that raises AttributeError, which — with no
    JSON error handler — Flask renders as an HTML 500 page. The frontend then
    fails to parse it, and the user sees
    "Unexpected token '<', "<!doctype "... is not valid JSON"
    instead of anything about the field that was empty.

    Every form in this app sends `field || null` for optional inputs, so null is
    the normal case, not an edge one.
    """
    if value is None:
        return default
    text = scrub(str(value)).strip()
    if not text:
        return default
    if max_len is not None and len(text) > max_len:
        raise ValidationError(f"{field} must be {max_len} characters or fewer.")
    return text


def clean_email(value, field: str = "Email") -> str:
    if value is None:
        raise ValidationError(f"{field} is required.")
    text = scrub(str(value)).strip().lower()
    if not text:
        raise ValidationError(f"{field} is required.")
    if len(text) > MAX_EMAIL_LEN:
        raise ValidationError(f"{field} must be {MAX_EMAIL_LEN} characters or fewer.")
    if not _EMAIL_RE.match(text):
        raise ValidationError("Enter a valid email address.")
    return text


def clean_password(value, field: str = "Password") -> str:
    """Bounds only — never trimmed, never normalised.

    A password is a byte sequence the user chose, and altering it here would
    mean the value stored at registration differs from the one checked at
    sign-in. Leading and trailing spaces are legitimate characters in a
    passphrase.
    """
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text.")
    if len(value) < MIN_PASSWORD_LEN:
        raise ValidationError(
            f"{field} must be at least {MIN_PASSWORD_LEN} characters long.")
    if len(value) > MAX_PASSWORD_LEN:
        raise ValidationError(
            f"{field} must be {MAX_PASSWORD_LEN} characters or fewer.")
    if "\x00" in value:
        raise ValidationError(f"{field} contains an invalid character.")
    return value


def clean_int(value, field: str = "value", minimum: int = None,
              maximum: int = None, default=None):
    if value is None or value == "":
        return default
    # bool is an int subclass; True would otherwise sail through as 1.
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be a whole number.")
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a whole number.")
    if minimum is not None and n < minimum:
        raise ValidationError(f"{field} must be {minimum} or greater.")
    if maximum is not None and n > maximum:
        raise ValidationError(f"{field} must be {maximum} or less.")
    return n


def clean_float(value, field: str = "value", minimum: float = None,
                maximum: float = None, default=None):
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be a number.")
    try:
        n = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number.")
    # NaN fails every comparison, so it would slip past a bounds check and then
    # poison any sort or aggregate it reaches.
    if n != n or n in (float("inf"), float("-inf")):
        raise ValidationError(f"{field} must be a number.")
    if minimum is not None and n < minimum:
        raise ValidationError(f"{field} must be {minimum} or greater.")
    if maximum is not None and n > maximum:
        raise ValidationError(f"{field} must be {maximum} or less.")
    return n


def clean_enum(value, allowed, field: str = "value", default=None,
               lower: bool = True):
    if value is None or value == "":
        return default
    text = scrub(str(value)).strip()
    if lower:
        text = text.lower()
    if text not in allowed:
        raise ValidationError(
            f"{field} must be one of: {', '.join(str(a) for a in allowed)}.")
    return text


def clean_date(value, field: str = "date", default=None,
               not_future: bool = False):
    if value is None or value == "":
        return default
    if isinstance(value, date):
        d = value
    else:
        try:
            d = date.fromisoformat(scrub(str(value)).strip())
        except (TypeError, ValueError):
            raise ValidationError(f"{field} must be a date in YYYY-MM-DD format.")
    if not_future and d > date.today():
        raise ValidationError(f"{field} cannot be in the future.")
    return d


def clean_text_block(value, field: str = "text", max_words: int = None,
                     max_chars: int = None, default=None):
    """A multi-line free-text field, bounded by both words and characters.

    Both limits, because they fail differently: a word count is what a user is
    shown and can reason about ("200 words"), and a character count is what
    actually bounds the storage — 200 "words" of pasted base64 is one word to a
    word counter and a megabyte to the database.
    """
    text = clean_str(value, default=None, max_len=max_chars, field=field)
    if text is None:
        return default
    if max_words is not None and len(text.split()) > max_words:
        raise ValidationError(f"{field} must be {max_words} words or fewer.")
    return text
