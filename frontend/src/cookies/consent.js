// The visitor's cookie choice.
//
// Stored in localStorage rather than in a cookie. That is deliberate and worth
// stating plainly: a consent record kept in a cookie is itself a cookie you
// have to justify, and storing the choice on the device rather than sending it
// to the server means it is never personal data we hold. Clearing site data
// clears the choice, and the banner asks again — which is the correct
// behaviour, not a bug.
//
// COOKIE_POLICY_VERSION must match the constant of the same name in
// app/legal.py and frontend/src/legal/privacy.js. A stored choice is only valid
// for the policy it was given against: bump the version when the cookies
// themselves change and every visitor is asked again.

import { COOKIE_POLICY_VERSION } from '../legal/privacy'

const STORAGE_KEY = 'fighthub_cookie_consent'

/**
 * The categories the banner offers.
 *
 * `locked` — cannot be turned off. The session cookie is strictly necessary
 * under PECR, so it is set on that exemption rather than on consent, and
 * pretending otherwise with a switch that does nothing would be the dishonest
 * option.
 *
 * `available: false` — the category is listed but unused, so its toggle is
 * shown disabled and off. Listing them is not theatre: it tells the visitor
 * what we are not doing, and it means the day one is actually adopted the
 * banner already asks properly rather than being retrofitted in a hurry.
 */
export const CATEGORIES = [
  {
    id: 'necessary',
    label: 'Strictly necessary',
    locked: true,
    available: true,
    description:
      'One session cookie that keeps you signed in. Without it the platform cannot tell one signed-in user from another, so it cannot be switched off while you are using the site. It expires after 8 hours and is never used for tracking.',
  },
  {
    id: 'analytics',
    label: 'Analytics',
    locked: false,
    available: false,
    description:
      'Would measure how the site is used so it can be improved. We do not currently use any analytics, so there is nothing here to switch on.',
  },
  {
    id: 'marketing',
    label: 'Marketing',
    locked: false,
    available: false,
    description:
      'Would support advertising and re-targeting. FightHub carries no advertising and we have no plans to, so there is nothing here to switch on.',
  },
]

/** The categories that are always on, whatever the visitor chooses. */
const NECESSARY = Object.fromEntries(
  CATEGORIES.filter(c => c.locked).map(c => [c.id, true]),
)

/** Every optional category off — what "Reject all" stores. */
export const REJECT_ALL = {
  ...NECESSARY,
  ...Object.fromEntries(CATEGORIES.filter(c => !c.locked).map(c => [c.id, false])),
}

/** Every optional category the site actually offers, on. Unavailable ones stay
 *  off: accepting a category we do not operate would record a consent we have
 *  no use for and could later act on without asking again. */
export const ACCEPT_ALL = {
  ...NECESSARY,
  ...Object.fromEntries(
    CATEGORIES.filter(c => !c.locked).map(c => [c.id, c.available]),
  ),
}

/**
 * The stored choice, or null if there is none to honour.
 *
 * Returns null — meaning "ask" — when storage is unavailable, when the record
 * is unreadable, and when it was given against an older version of the policy.
 * Every one of those is a case where we do not have a valid choice on file, and
 * the safe response to that is to ask rather than to assume.
 */
export function readConsent() {
  let raw
  try {
    raw = window.localStorage.getItem(STORAGE_KEY)
  } catch {
    // Private browsing, or site data blocked. Nothing is stored, so nothing
    // optional may be set — the banner will simply ask on every visit.
    return null
  }
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw)
    if (parsed?.version !== COOKIE_POLICY_VERSION) return null
    if (!parsed?.categories) return null
    return parsed
  } catch {
    return null
  }
}

/**
 * Record a choice. Returns false if it could not be stored, so the caller can
 * dismiss the banner for this page view without claiming the choice was saved.
 */
export function writeConsent(categories) {
  const record = {
    version: COOKIE_POLICY_VERSION,
    categories: { ...categories, ...NECESSARY },
    timestamp: new Date().toISOString(),
  }
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(record))
    return true
  } catch {
    return false
  }
}

/** Forget the stored choice, so the banner asks again. Used by "Withdraw my
 *  choice" in the profile — withdrawal has to be as easy as giving it. */
export function clearConsent() {
  try {
    window.localStorage.removeItem(STORAGE_KEY)
    return true
  } catch {
    return false
  }
}

/** Is this optional category permitted right now? The gate any future
 *  analytics or marketing script must pass through before it loads. */
export function isAllowed(categoryId) {
  if (NECESSARY[categoryId]) return true
  return readConsent()?.categories?.[categoryId] === true
}
