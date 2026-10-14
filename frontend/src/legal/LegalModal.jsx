import { useEffect, useRef, useState } from 'react'
import LegalDocument from './LegalDocument'

/**
 * A legal document in a dialog, in one of two modes.
 *
 * `consent` — shown before an account is created. The Agree button stays
 * disabled until the document has actually been scrolled to the end. That is
 * the pattern used by banking and app-store sign-ups, and it is what makes
 * "the user was given the chance to read this" a defensible claim rather than
 * an assumption — a tick box next to a link proves only that a box was ticked.
 * Declining is always available and always one click: a dialog that traps the
 * user until they agree is not freely given consent.
 *
 * `read` — the same document, reached from the profile or a footer link by
 * someone who has already agreed and simply wants to re-read it. No gate, no
 * decision to make, one Close button. Gating a document somebody opened
 * voluntarily would be pure obstruction.
 */
export default function LegalModal({
  doc, mode = 'read', onAgree, onClose,
  agreeLabel = 'I agree', progress,
}) {
  const scrollRef = useRef(null)
  const closeRef = useRef(null)
  const isConsent = mode === 'consent'
  const [atEnd, setAtEnd] = useState(false)

  // Lock the page behind the dialog so scrolling the wheel moves the document,
  // not the form underneath.
  useEffect(() => {
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    closeRef.current?.focus()
    return () => { document.body.style.overflow = prev }
  }, [])

  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // Reset the gate when the dialog is reused for a second document, otherwise
  // having read the terms would count as having read the privacy notice.
  useEffect(() => {
    setAtEnd(false)
    scrollRef.current?.scrollTo({ top: 0 })
  }, [doc.key])

  function onScroll(e) {
    const { scrollTop, scrollHeight, clientHeight } = e.target
    // 24px of slack: sub-pixel rounding and zoom levels mean scrollTop often
    // lands just short of the exact bottom, which would leave the button
    // permanently disabled for some users.
    if (scrollTop + clientHeight >= scrollHeight - 24) setAtEnd(true)
  }

  // A short document on a tall screen may not scroll at all, in which case it
  // is already fully visible and the gate would never open.
  useEffect(() => {
    const el = scrollRef.current
    if (el && el.scrollHeight <= el.clientHeight + 24) setAtEnd(true)
  }, [doc.key])

  function jumpToEnd() {
    const el = scrollRef.current
    el?.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }

  return (
    <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="modal legal-modal" role="dialog" aria-modal="true" aria-labelledby="legal-title">
        <div className="legal-modal-head">
          <h2 id="legal-title">
            {doc.title}
            {progress && <span className="legal-progress"> · {progress}</span>}
          </h2>
          <button ref={closeRef} className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="legal-modal-body" ref={scrollRef} onScroll={onScroll} tabIndex={0}>
          <LegalDocument sections={doc.sections} version={doc.version} updated={doc.updated} />
        </div>

        <div className="legal-modal-foot">
          {isConsent && !atEnd && (
            <button type="button" className="legal-jump" onClick={jumpToEnd}>
              ↓ Scroll to the end to continue
            </button>
          )}
          <div className="legal-modal-actions">
            {isConsent ? (
              <>
                <button type="button" className="btn" onClick={onClose}>Decline</button>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!atEnd}
                  title={atEnd ? undefined : 'Please read to the end of the document first'}
                  onClick={onAgree}
                >
                  {agreeLabel}
                </button>
              </>
            ) : (
              <button type="button" className="btn btn-primary" onClick={onClose}>Close</button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
