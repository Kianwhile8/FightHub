import { Link } from 'react-router-dom'
import LegalDocument from '../legal/LegalDocument'
import { TERMS_DOC, PRIVACY_DOC, COOKIE_DOC } from '../legal/documents'

/**
 * A legal document at a stable, linkable URL, outside the protected routes.
 *
 * These have to be reachable without an account: a prospective user deciding
 * whether to sign up, and a former user checking what they agreed to, both need
 * to read them, and neither can log in to do so.
 *
 * The three documents cross-link to each other, because someone who arrives at
 * the cookie policy from the banner usually wants the privacy notice next.
 */
function LegalPage({ doc }) {
  const others = [TERMS_DOC, PRIVACY_DOC, COOKIE_DOC].filter(d => d.key !== doc.key)

  return (
    <div className="legal-page">
      <Link to="/login" className="legal-back">← Back to sign in</Link>
      <h1>{doc.title}</h1>
      <LegalDocument sections={doc.sections} version={doc.version} updated={doc.updated} />
      <p className="legal-crosslinks">
        See also:{' '}
        {others.map((d, i) => (
          <span key={d.key}>
            {i > 0 && ' · '}
            <Link to={d.path}>{d.title}</Link>
          </span>
        ))}
      </p>
    </div>
  )
}

export function TermsPage()   { return <LegalPage doc={TERMS_DOC} /> }
export function PrivacyPage() { return <LegalPage doc={PRIVACY_DOC} /> }
export function CookiesPage() { return <LegalPage doc={COOKIE_DOC} /> }
