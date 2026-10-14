import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch, apiUpload } from '../api/client'
import { useAuthStore } from '../store/auth'
import Spinner from '../components/Spinner'
import { useEntitlement } from '../hooks/useEntitlement'
import CookieBanner from '../components/CookieBanner'
import LegalModal from '../legal/LegalModal'
import { TERMS_DOC, PRIVACY_DOC, COOKIE_DOC } from '../legal/documents'

const LEGAL_DOCS = [TERMS_DOC, PRIVACY_DOC, COOKIE_DOC]

/** "19 September 2026" from an ISO timestamp, or null. */
function formatDate(iso) {
  if (!iso) return null
  const d = new Date(iso)
  return Number.isNaN(d.getTime())
    ? null
    : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

export default function Profile() {
  const { user, setUser } = useAuthStore()
  const qc = useQueryClient()
  const fileRef = useRef(null)
  const [openDoc, setOpenDoc] = useState(null)
  const [showCookiePrefs, setShowCookiePrefs] = useState(false)
  const [showDeleteForm, setShowDeleteForm] = useState(false)

  const { data: meData, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: () => apiFetch('/api/auth/me'),
  })

  const { data: delData } = useQuery({
    queryKey: ['deletion-request'],
    queryFn: () => apiFetch('/api/auth/deletion-request'),
  })
  const pendingDeletion = delData?.request ?? null

  const requestDeletion = useMutation({
    mutationFn: (body) => apiFetch('/api/auth/deletion-request', {
      method: 'POST', body: JSON.stringify(body),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['deletion-request'] })
      setShowDeleteForm(false)
      toast.success('Deletion request submitted. We will complete it within 30 days.')
    },
    onError: (e) => toast.error(e.message),
  })

  const cancelDeletion = useMutation({
    mutationFn: () => apiFetch('/api/auth/deletion-request', { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['deletion-request'] })
      toast.success('Deletion request cancelled.')
    },
    onError: (e) => toast.error(e.message),
  })

  const privacyMutation = useMutation({
    mutationFn: (hide) => apiFetch('/api/auth/privacy', { method: 'PUT', body: JSON.stringify({ hide_record: hide }) }),
    onSuccess: (d) => { setUser(d.user); qc.invalidateQueries({ queryKey: ['me'] }); toast.success('Privacy updated.') },
    onError: (e) => toast.error(e.message),
  })

  const pwMutation = useMutation({
    mutationFn: (body) => apiFetch('/api/auth/change-password', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => toast.success('Password changed.'),
    onError: (e) => toast.error(e.message),
  })

  const avatarMutation = useMutation({
    mutationFn: (file) => apiUpload('/api/upload/avatar', file),
    onSuccess: (d) => {
      setUser(d.user)
      qc.invalidateQueries({ queryKey: ['me'] })
      toast.success('Profile picture updated.')
    },
    onError: (e) => toast.error(e.message),
  })

  function handlePw(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    if (fd.get('new_password') !== fd.get('confirm')) { toast.error('Passwords do not match.'); return }
    pwMutation.mutate({ old_password: fd.get('old_password'), new_password: fd.get('new_password') })
    e.target.reset()
  }

  function handleAvatarChange(e) {
    const file = e.target.files?.[0]
    if (file) avatarMutation.mutate(file)
  }

  function handleDeleteRequest(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    // Typing the word is a deliberate speed bump. The password alone would be
    // muscle memory; this makes the action hard to take by accident.
    if (fd.get('confirm') !== 'DELETE') {
      toast.error('Type DELETE to confirm.')
      return
    }
    requestDeletion.mutate({
      password: fd.get('password'),
      reason: fd.get('reason')?.trim() || null,
    })
  }

  if (isLoading) return <Spinner />

  const me  = meData?.user ?? user
  const rec = me?.fighter_record
  const picUrl = me?.profile_picture ? `/uploads/${me.profile_picture}` : null

  return (
    <>
      <h1>My Profile</h1>

      <div className="card">
        <div className="user-info" style={{ marginBottom: '1rem', gap: 16 }}>
          <div style={{ position: 'relative', flexShrink: 0 }}>
            {picUrl
              ? <img src={picUrl} alt="Profile" style={{ width: 56, height: 56, borderRadius: '50%',
                  objectFit: 'cover', border: '2px solid var(--border)' }} />
              : <div className="user-avatar" style={{ width: 56, height: 56, fontSize: 20 }}>
                  {me?.email?.[0]?.toUpperCase()}
                </div>
            }
            <button
              title="Change photo"
              onClick={() => fileRef.current?.click()}
              disabled={avatarMutation.isPending}
              style={{ position: 'absolute', bottom: -4, right: -4, width: 22, height: 22,
                borderRadius: '50%', background: 'var(--accent)', border: 'none',
                cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 12, color: '#fff', padding: 0 }}>
              {avatarMutation.isPending ? '…' : '✎'}
            </button>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp"
              style={{ display: 'none' }} onChange={handleAvatarChange} />
          </div>
          <div>
            <div style={{ fontWeight: 500 }}>{me?.email}</div>
            <span className="user-role-badge">{me?.role}</span>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
              Click the pencil icon to upload a profile photo (PNG / JPG / WebP, max 5 MB)
            </div>
          </div>
        </div>

        {me?.role === 'fighter' && (
          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', fontSize: 14 }}>
            <input type="checkbox" checked={!!me?.hide_record}
              onChange={e => privacyMutation.mutate(e.target.checked)} style={{ width: 'auto' }} />
            Hide my fight record from other users
          </label>
        )}
      </div>

      {rec && (
        <div className="card">
          <h2>Fighter Record — {me.fighter_sport?.toUpperCase()}</h2>
          <div className="detail-grid">
            <div className="stat">
              <div className="stat-val" style={{ color: 'var(--success)' }}>{rec.wins ?? 0}</div>
              <div className="stat-lbl">Wins</div>
            </div>
            <div className="stat">
              <div className="stat-val" style={{ color: 'var(--danger)' }}>{rec.losses ?? 0}</div>
              <div className="stat-lbl">Losses</div>
            </div>
            <div className="stat"><div className="stat-val">{rec.draws ?? 0}</div><div className="stat-lbl">Draws</div></div>
            <div className="stat"><div className="stat-val">{rec.weight_kg}kg</div><div className="stat-lbl">Weight</div></div>
          </div>
        </div>
      )}

      <div className="card">
        <h2>Change Password</h2>
        <form onSubmit={handlePw}>
          <div className="form-group">
            <label className="form-label">Current password</label>
            <input name="old_password" type="password" required />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label className="form-label">New password</label>
              <input name="new_password" type="password" required />
            </div>
            <div className="form-group">
              <label className="form-label">Confirm new password</label>
              <input name="confirm" type="password" required />
            </div>
          </div>
          <button type="submit" className="btn btn-primary btn-sm" disabled={pwMutation.isPending}>
            {pwMutation.isPending ? 'Saving…' : 'Change Password'}
          </button>
        </form>
      </div>

      {/* Not gated — this page is all own-account scope. The card is here
          because "where do I pay / cancel" is an account question, and the
          sidebar entry alone is easy to miss. */}
      {me.role !== 'admin' && (
        <div className="card">
          <h2>Subscription</h2>
          <SubscriptionSummary />
        </div>
      )}

      <div className="card">
        <h2>Legal &amp; data</h2>

        <p className="card-lead">
          The documents you agreed to when you created your account. They are
          here so you can re-read them whenever you like, not only at sign-up.
        </p>

        <div className="legal-links">
          {LEGAL_DOCS.map(d => (
            <div key={d.key} className="legal-link-row">
              <div>
                <button type="button" className="legal-link-title"
                  onClick={() => setOpenDoc(d)}>
                  {d.title}
                </button>
                <div className="legal-link-meta">Version {d.version}</div>
              </div>
              <Link to={d.path} target="_blank" rel="noopener noreferrer"
                className="terms-link">Open in a new tab ↗</Link>
            </div>
          ))}
        </div>

        <div className="legal-accepted">
          {formatDate(me?.terms_accepted_at) && (
            <div>
              Terms of Service accepted on {formatDate(me.terms_accepted_at)}
              {me.terms_version && ` (version ${me.terms_version})`}
            </div>
          )}
          {formatDate(me?.privacy_accepted_at) && (
            <div>
              Privacy Notice acknowledged on {formatDate(me.privacy_accepted_at)}
              {me.privacy_version && ` (version ${me.privacy_version})`}
            </div>
          )}
        </div>

        <div className="legal-actions">
          <button type="button" className="btn btn-sm"
            onClick={() => setShowCookiePrefs(true)}>
            Cookie preferences
          </button>
        </div>
      </div>

      <div className="card card--danger">
        <h2>Delete your account</h2>

        {pendingDeletion ? (
          <>
            <p className="card-lead">
              Your deletion request was received on{' '}
              {formatDate(pendingDeletion.requested_at)} and is waiting to be
              actioned. We will complete it within {pendingDeletion.sla_days} days
              of the request.
            </p>
            <p className="card-lead">
              You can change your mind until it is actioned — cancelling leaves
              your account exactly as it is.
            </p>
            <button type="button" className="btn btn-sm"
              disabled={cancelDeletion.isPending}
              onClick={() => cancelDeletion.mutate()}>
              {cancelDeletion.isPending ? 'Cancelling…' : 'Cancel deletion request'}
            </button>
          </>
        ) : !showDeleteForm ? (
          <>
            <p className="card-lead">
              You can ask us to delete your account and your personal data at any
              time. You do not have to give a reason.
            </p>
            <p className="card-lead">
              The request goes to an administrator rather than taking effect
              immediately, because a deletion reaches into other people's
              competitive records. We will complete it within 30 days, and you
              can cancel it at any point before then. Bout results stay on your
              opponents' records, anonymised so they no longer identify you.
              What is removed, and the little that is kept, is set out in{' '}
              <button type="button" className="terms-link"
                onClick={() => setOpenDoc(PRIVACY_DOC)}>
                section 7 of the Privacy Notice
              </button>.
            </p>
            <button type="button" className="btn btn-danger btn-sm"
              onClick={() => setShowDeleteForm(true)}>
              Request account deletion
            </button>
          </>
        ) : (
          <form onSubmit={handleDeleteRequest}>
            <p className="card-lead">
              Confirm with your password. Nothing is deleted at this point — the
              request is queued for an administrator.
            </p>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Your password</label>
                <input name="password" type="password" required autoComplete="current-password" />
              </div>
              <div className="form-group">
                <label className="form-label">Type DELETE to confirm</label>
                <input name="confirm" required autoComplete="off" placeholder="DELETE" />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Reason (optional)</label>
              <textarea name="reason" rows={2} maxLength={1000}
                placeholder="You do not have to give one."
                style={{ resize: 'vertical' }} />
            </div>
            <div style={{ display: 'flex', gap: '.5rem' }}>
              <button type="button" className="btn btn-sm"
                onClick={() => setShowDeleteForm(false)}>Cancel</button>
              <button type="submit" className="btn btn-danger btn-sm"
                disabled={requestDeletion.isPending}>
                {requestDeletion.isPending ? 'Submitting…' : 'Submit deletion request'}
              </button>
            </div>
          </form>
        )}
      </div>

      {openDoc && (
        <LegalModal doc={openDoc} mode="read" onClose={() => setOpenDoc(null)} />
      )}

      {showCookiePrefs && (
        <CookieBanner forceOpen onClose={() => setShowCookiePrefs(false)} />
      )}
    </>
  )
}

/** The account's subscription state, with a link to do something about it.
 *
 *  Reads the store rather than fetching: /api/auth/me already supplied this at
 *  boot, and the billing page is one click away for the authoritative view.
 */
function SubscriptionSummary() {
  const { state, trial_days_left: daysLeft, current_period_end: periodEnd,
          cancel_at_period_end: cancelling, comp_reason: compReason } = useEntitlement()

  const pill = {
    active:   ['sub-pill--active',   'Active'],
    trialing: ['sub-pill--trialing', 'Free trial'],
    comped:   ['sub-pill--comped',   'Complimentary'],
    past_due: ['sub-pill--past-due', 'Payment failed'],
    expired:  ['sub-pill--expired',  'Ended'],
    none:     ['sub-pill--none',     'No subscription'],
  }[state] || ['sub-pill--none', 'Unknown']

  const renews = periodEnd ? formatDate(periodEnd) : null

  let line
  if (state === 'trialing') {
    line = `Your free trial has ${daysLeft === 1 ? '1 day' : `${daysLeft ?? 0} days`} left.`
  } else if (state === 'active' && cancelling) {
    line = `Cancelled — you keep access until ${renews}.`
  } else if (state === 'active') {
    line = renews ? `Renews on ${renews}.` : 'Your subscription is active.'
  } else if (state === 'past_due') {
    line = 'We could not take your renewal payment. Update your card to keep access.'
  } else if (state === 'comped') {
    line = compReason
      ? `Complimentary access (${compReason}). Nothing to pay.`
      : 'Complimentary access. Nothing to pay.'
  } else {
    line = 'FightHub is read-only on your account. Browsing stays free.'
  }

  return (
    <>
      <div className="sub-status">
        <span className={`sub-pill ${pill[0]}`}>{pill[1]}</span>
      </div>
      <p className="card-lead">{line}</p>
      <Link className="btn btn-sm" to="/billing">Manage subscription</Link>
    </>
  )
}
