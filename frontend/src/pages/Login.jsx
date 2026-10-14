import { useState } from 'react'
import { useNavigate, Navigate, Link, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import { apiFetch } from '../api/client'
import { useAuthStore } from '../store/auth'
import LegalModal from '../legal/LegalModal'
import { CONSENT_DOCS } from '../legal/documents'
import SegmentedToggle from '../components/SegmentedToggle'
import { ACCOUNT_GENDER_OPTIONS } from '../constants/gender'
import { lastSport } from '../constants/sports'

const ROLES = [
  { id: 'fighter',  icon: '🥊', label: 'Fighter',  desc: 'Track my record' },
  { id: 'coach',    icon: '🏋️', label: 'Coach',    desc: 'Manage fighters' },
  { id: 'promoter', icon: '📋', label: 'Promoter', desc: 'Run events' },
]

export default function Login() {
  const { user, ready, setSession } = useAuthStore()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  // `?tab=register` lets the landing page's calls to action open the sign-up
  // form directly. Read once as the initial value rather than tracked: the tab
  // buttons below own this state afterwards, and re-syncing it to the URL would
  // fight the user every time they clicked "Sign in".
  const [tab, setTab] = useState(params.get('tab') === 'register' ? 'register' : 'login')
  const [loading, setLoading] = useState(false)
  const [agreed, setAgreed] = useState(false)
  // Which document of CONSENT_DOCS is open, as an index; null when none is.
  // Agreeing to one advances to the next, so the walk-through is just this
  // index moving along the list.
  const [docIndex, setDocIndex] = useState(null)
  // Role is held here rather than inside RoleSelect because the gender
  // question depends on it: only fighters are asked.
  const [role, setRole] = useState('')
  const [gender, setGender] = useState('')

  if (ready && user) return <Navigate to={`/${lastSport()}/dashboard`} replace />

  async function submit(path, body) {
    setLoading(true)
    try {
      const d = await apiFetch(path, { method: 'POST', body: JSON.stringify(body) })
      // Both at once: a render where the user is known but the entitlement is
      // not would flash the trial banner at someone who has paid.
      setSession(d.user, d.entitlement)
      navigate(`/${lastSport()}/dashboard`)
    } catch (e) {
      toast.error(e.message)
    } finally {
      setLoading(false)
    }
  }

  function onLogin(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    submit('/api/auth/login', { email: fd.get('email'), password: fd.get('password') })
  }

  function onRegister(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    if (!role) { toast.error('Please select a role.'); return }
    // The server rejects this too. The check here is only so the user gets an
    // immediate answer instead of a round trip.
    if (!agreed) {
      toast.error('Please read and accept the terms and privacy notice to create an account.')
      setDocIndex(0)
      return
    }
    submit('/api/auth/register', {
      email: fd.get('email'),
      password: fd.get('password'),
      role,
      accept_terms: true,
      // Omitted entirely for coaches and promoters — the server discards it
      // for those roles regardless, but there is no reason to send it.
      ...(role === 'fighter' && gender ? { gender } : {}),
    })
  }

  // Agreement is only complete once every document has been read to the end.
  function agreeToCurrent() {
    const next = docIndex + 1
    if (next < CONSENT_DOCS.length) {
      setDocIndex(next)
    } else {
      setAgreed(true)
      setDocIndex(null)
    }
  }

  const openDoc = docIndex != null ? CONSENT_DOCS[docIndex] : null
  const isLastDoc = docIndex === CONSENT_DOCS.length - 1

  return (
    <div className="auth-screen">
      <div className="auth-box">
        <div className="auth-logo">Fight<span style={{ color: 'var(--muted)', fontWeight: 400 }}>Hub</span></div>
        <div className="auth-sub">Amateur combat sports management</div>

        <div className="auth-tabs">
          {['login', 'register'].map(t => (
            <button key={t} className={`auth-tab${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>
              {t === 'login' ? 'Sign in' : 'Create account'}
            </button>
          ))}
        </div>

        {tab === 'login' ? (
          <form onSubmit={onLogin}>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input name="email" type="email" required autoFocus />
            </div>
            <div className="form-group">
              <label className="form-label">Password</label>
              <input name="password" type="password" required />
            </div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        ) : (
          <form onSubmit={onRegister}>
            <div className="form-group">
              <label className="form-label">Email</label>
              <input name="email" type="email" required autoFocus />
            </div>
            <div className="form-group">
              <label className="form-label">Password</label>
              <input name="password" type="password" required minLength={8} />
            </div>
            <div className="form-group">
              <label className="form-label">I am a…</label>
              <RoleSelect value={role} onChange={setRole} />
            </div>

            {/* Asked of fighters only. A coach or promoter has no competitive
                division, so the answer would have no use — and data with no
                use is data we should not be holding. */}
            {role === 'fighter' && (
              <div className="form-group">
                <label className="form-label">Gender</label>
                <SegmentedToggle
                  label="Gender"
                  options={ACCOUNT_GENDER_OPTIONS}
                  value={gender}
                  onChange={setGender}
                />
                <div className="form-hint">
                  Combat sports are contested in single-sex divisions, so this is
                  what lets us pair you safely. You can decline, and you can
                  change it later on your fighter profile.
                </div>
              </div>
            )}

            <div className="terms-consent">
              <input
                id="accept-terms"
                type="checkbox"
                checked={agreed}
                // Ticking the box directly is allowed, but it opens the
                // documents rather than silently agreeing: the box can only
                // ever be set by someone who has been shown the text.
                onChange={e => { if (e.target.checked) { setDocIndex(0) } else { setAgreed(false) } }}
              />
              <label htmlFor="accept-terms">
                I have read and agree to the{' '}
                <button type="button" className="terms-link" onClick={() => setDocIndex(0)}>
                  Terms of Service
                </button>
                {' '}and the{' '}
                <button type="button" className="terms-link" onClick={() => setDocIndex(1)}>
                  Privacy Notice
                </button>
                , including that my fighter profile and competitive record are
                visible to other users.
                <span className="terms-consent-links">
                  {CONSENT_DOCS.map(d => (
                    <Link key={d.key} to={d.path} target="_blank" rel="noopener noreferrer"
                      className="terms-link">
                      {d.title} ↗
                    </Link>
                  ))}
                </span>
              </label>
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%' }} disabled={loading || !agreed}>
              {loading ? 'Creating account…' : 'Create account'}
            </button>
          </form>
        )}
      </div>

      {openDoc && (
        <LegalModal
          doc={openDoc}
          mode="consent"
          progress={`${docIndex + 1} of ${CONSENT_DOCS.length}`}
          agreeLabel={isLastDoc ? 'I agree' : 'I agree — continue'}
          onAgree={agreeToCurrent}
          onClose={() => setDocIndex(null)}
        />
      )}
    </div>
  )
}

function RoleSelect({ value, onChange }) {
  return (
    <div className="role-select">
      {ROLES.map(r => (
        <div key={r.id} className={`role-card${value === r.id ? ' selected' : ''}`}
          onClick={() => onChange(r.id)}>
          <div className="role-card-icon">{r.icon}</div>
          <div className="role-card-label">{r.label}</div>
          <div className="role-card-desc">{r.desc}</div>
        </div>
      ))}
    </div>
  )
}
