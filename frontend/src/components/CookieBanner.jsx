import { useEffect, useState } from 'react'
import {
  CATEGORIES, ACCEPT_ALL, REJECT_ALL, readConsent, writeConsent,
} from '../cookies/consent'

/**
 * Cookie consent banner.
 *
 * Follows the conventional three-action pattern — Reject all, Preferences,
 * Accept all — with the two decline paths given the same weight as the accept
 * path. Reject is a button of equal prominence, not a link hidden under a
 * preferences panel, because a refusal that is harder to give than an
 * acceptance is not freely given.
 *
 * FightHub currently sets one strictly necessary cookie and nothing else, so
 * in practice all three buttons produce the same cookies. The banner says so
 * rather than implying a choice that does not exist: the necessary category is
 * shown as always active, and the unused categories are listed but disabled.
 * The structure is here so that the day an optional cookie is actually adopted,
 * consent is already being collected properly.
 *
 * `forceOpen` lets the profile reopen it so a stored choice can be changed,
 * which is the withdrawal route the policy promises.
 */
// The profile can open a second instance of this banner to change a stored
// choice. If the visitor had not dismissed the first one yet, both would render
// as a fixed bottom bar and stack on top of each other. The forced instance
// announces itself, and the automatic one steps aside while it is open.
const PREFS_EVENT = 'fighthub:cookie-prefs'

export default function CookieBanner({ forceOpen = false, onClose }) {
  const [visible, setVisible] = useState(false)
  const [showPrefs, setShowPrefs] = useState(false)
  const [choices, setChoices] = useState(REJECT_ALL)
  const [supersededByPrefs, setSupersededByPrefs] = useState(false)

  useEffect(() => {
    if (forceOpen) {
      const stored = readConsent()
      setChoices(stored?.categories ?? REJECT_ALL)
      setShowPrefs(true)
      setVisible(true)
      window.dispatchEvent(new CustomEvent(PREFS_EVENT, { detail: { open: true } }))
      return () => window.dispatchEvent(
        new CustomEvent(PREFS_EVENT, { detail: { open: false } }))
    }
    // Only ask when there is no valid choice on file. readConsent() already
    // treats an expired policy version and unreadable storage as "no choice".
    if (!readConsent()) setVisible(true)
    const onPrefs = (e) => setSupersededByPrefs(!!e.detail?.open)
    window.addEventListener(PREFS_EVENT, onPrefs)
    return () => window.removeEventListener(PREFS_EVENT, onPrefs)
  }, [forceOpen])

  // The banner is fixed to the bottom of the viewport, so on a short screen it
  // sits on top of whatever is down there — including the Create account
  // button, which is the one control a first-time visitor needs and the one
  // most likely to be underneath it. The class opens up enough scrollable room
  // below the content to reach past it.
  // Follows what is actually on screen, not just `visible` — the automatic
  // banner keeps `visible` true while it steps aside for the profile's one, and
  // toggling the class off from here would then fight the other instance.
  const onScreen = visible && !supersededByPrefs
  useEffect(() => {
    const cls = 'has-cookie-banner'
    if (!onScreen) return undefined
    document.body.classList.add(cls)
    return () => document.body.classList.remove(cls)
  }, [onScreen])

  if (!onScreen) return null

  function decide(categories) {
    writeConsent(categories)
    setVisible(false)
    setShowPrefs(false)
    onClose?.()
  }

  function dismiss() {
    // Closing the reopened panel without choosing leaves the stored choice
    // alone. Closing it on a first visit is not offered — there is no ✕ — so
    // this only ever runs from the profile.
    setVisible(false)
    setShowPrefs(false)
    onClose?.()
  }

  return (
    <div className="cookie-banner" role="dialog" aria-modal="false"
      aria-labelledby="cookie-banner-title">
      <div className="cookie-banner-inner">
        <div className="cookie-banner-text">
          <h2 id="cookie-banner-title" className="cookie-banner-title">
            Cookies on FightHub
          </h2>
          <p>
            We use one strictly necessary cookie to keep you signed in. We set no
            analytics, advertising or tracking cookies, and no third party sets
            any cookie through this site.{' '}
            {/* A plain anchor, not a router Link: the banner is mounted above
                the router so it can appear on every route, and opening the
                policy in a new tab means reading it does not interrupt
                whatever the visitor was part-way through. */}
            <a href="/cookies" target="_blank" rel="noopener noreferrer" className="terms-link">
              Read our Cookie Policy
            </a>.
          </p>
        </div>

        <div className="cookie-banner-actions">
          <button type="button" className="btn btn-sm"
            onClick={() => setShowPrefs(v => !v)}
            aria-expanded={showPrefs} aria-controls="cookie-prefs">
            Cookie preferences
          </button>
          <button type="button" className="btn btn-sm" onClick={() => decide(REJECT_ALL)}>
            Reject all
          </button>
          <button type="button" className="btn btn-primary btn-sm" onClick={() => decide(ACCEPT_ALL)}>
            Accept all
          </button>
        </div>
      </div>

      {showPrefs && (
        <div className="cookie-prefs" id="cookie-prefs">
          {CATEGORIES.map(c => {
            const checked = c.locked ? true : !!choices[c.id]
            return (
              <div key={c.id} className="cookie-cat">
                <label className="cookie-cat-head">
                  <input
                    type="checkbox"
                    checked={checked}
                    // Locked because it is strictly necessary; disabled because
                    // it is a category we do not operate. Two different reasons
                    // for the same visual state, both explained in the label.
                    disabled={c.locked || !c.available}
                    onChange={e => setChoices(p => ({ ...p, [c.id]: e.target.checked }))}
                  />
                  <span className="cookie-cat-label">{c.label}</span>
                  {c.locked
                    ? <span className="cookie-cat-tag">Always active</span>
                    : !c.available
                    ? <span className="cookie-cat-tag cookie-cat-tag--off">Not currently used</span>
                    : null}
                </label>
                <p className="cookie-cat-desc">{c.description}</p>
              </div>
            )
          })}

          <div className="cookie-prefs-foot">
            {forceOpen && (
              <button type="button" className="btn btn-sm" onClick={dismiss}>
                Cancel
              </button>
            )}
            <button type="button" className="btn btn-primary btn-sm"
              onClick={() => decide(choices)}>
              Save preferences
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
