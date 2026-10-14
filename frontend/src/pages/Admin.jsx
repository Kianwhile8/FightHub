// The admin panel. Three independent cards, each with its own requests:
//
//   DeletionRequestsCard  the erasure queue, with a 30-day deadline per request
//   UsersCard             every account: role, comp/revoke access, delete
//   WebhookEventsCard     recent Stripe webhook deliveries, for debugging
//
// The server enforces admin-only on every /api/admin route; the redirect
// below just keeps other roles off the page.

import { Navigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch } from '../api/client'
import { useAuthStore } from '../store/auth'
import { lastSport } from '../constants/sports'
import Spinner from '../components/Spinner'

const ROLES = ['fighter', 'coach', 'promoter', 'admin']

const roleColour = {
  admin: 'var(--accent-light)', coach: 'var(--success)',
  promoter: 'var(--warn)', fighter: 'var(--info)',
}

// Entitlement state -> [css modifier, label]. Mirrors BillingService's `state`.
const SUB_PILL = {
  active:   ['sub-pill--active',   'active'],
  trialing: ['sub-pill--trialing', 'trial'],
  comped:   ['sub-pill--comped',   'comped'],
  past_due: ['sub-pill--past-due', 'payment failed'],
  expired:  ['sub-pill--expired',  'expired'],
  none:     ['sub-pill--none',     'no plan'],
  admin:    ['sub-pill--admin',    'admin'],
}

// Webhook event status -> css modifier.
const WEBHOOK_PILL = {
  processed: 'sub-pill--active',
  failed:    'sub-pill--expired',
  ignored:   'sub-pill--none',
}

function SubPill({ ent }) {
  if (!ent) return null
  const [cls, label] = SUB_PILL[ent.state] || ['sub-pill--none', ent.state]
  const suffix = ent.state === 'trialing' && ent.trial_days_left != null
    ? ` · ${ent.trial_days_left}d`
    : ''
  return <span className={`sub-pill ${cls}`}>{label}{suffix}</span>
}

export default function Admin() {
  const { user } = useAuthStore()

  if (user?.role !== 'admin') return <Navigate to={`/${lastSport()}/dashboard`} replace />

  return (
    <>
      <h1>Admin Panel</h1>
      <DeletionRequestsCard />
      <UsersCard currentUserId={user.id} />
      <WebhookEventsCard />
    </>
  )
}

/** Pending erasure requests. Each must be completed (or refused, with a
 *  reason) within its SLA; rows turn amber at two-thirds and red when late. */
function DeletionRequestsCard() {
  const qc = useQueryClient()

  const { data: delData } = useQuery({
    queryKey: ['admin-deletion-requests'],
    queryFn: () => apiFetch('/api/admin/deletion-requests'),
  })

  const resolveMutation = useMutation({
    mutationFn: ({ id, action, note }) => apiFetch(
      `/api/admin/deletion-requests/${id}/${action}`,
      { method: 'POST', body: JSON.stringify({ note: note || null }) },
    ),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ['admin-deletion-requests'] })
      qc.invalidateQueries({ queryKey: ['admin-users'] })
      toast.success(vars.action === 'complete'
        ? 'Account erased and the request closed.'
        : 'Request refused.')
    },
    onError: (e) => toast.error(e.message),
  })

  const requests = delData?.requests ?? []

  return (
    <div className={`card${requests.length ? ' card--danger' : ''}`}>
      <h2>Deletion requests ({requests.length})</h2>
      <p className="card-lead">
        Erasure requests from account holders. Each must be completed within
        30 days of the date it was made — that is what the Privacy Notice
        commits to, so the deadline is a legal one, not a target.
      </p>

      {requests.length === 0
        ? <div className="empty">No pending requests.</div>
        : requests.map(r => {
          const overdue = r.days_open >= r.sla_days
          const soon = !overdue && r.days_open >= Math.floor(r.sla_days * 0.66)
          return (
            <div key={r.id} className="deletion-row">
              <div className="deletion-main">
                <div className="deletion-email">{r.user_email ?? `User ${r.user_id}`}</div>
                <div className="deletion-meta">
                  Requested {new Date(r.requested_at).toLocaleDateString('en-GB')}
                  {' · '}
                  <span className={overdue ? 'sla-over' : soon ? 'sla-soon' : ''}>
                    {r.days_open === 0 ? 'today' : `${r.days_open} day${r.days_open === 1 ? '' : 's'} ago`}
                    {overdue && ' — past the 30-day deadline'}
                  </span>
                </div>
                {r.reason && <div className="deletion-reason">“{r.reason}”</div>}
              </div>
              <div className="deletion-actions">
                <button className="btn btn-sm"
                  disabled={resolveMutation.isPending}
                  onClick={() => {
                    const note = window.prompt(
                      'Refusing a deletion request is lawful only in narrow cases, and the ' +
                      'requester is entitled to be told why. Reason:')
                    if (note?.trim()) resolveMutation.mutate({ id: r.id, action: 'reject', note })
                  }}>
                  Refuse
                </button>
                <button className="btn btn-danger btn-sm"
                  disabled={resolveMutation.isPending}
                  onClick={() => {
                    if (window.confirm(
                      `Erase ${r.user_email ?? 'this account'} and all of its personal data?\n\n` +
                      'Their fighter profiles, record and photographs are removed. Bout results ' +
                      'on opponents’ records are kept but anonymised.\n\nThis cannot be undone.'))
                      resolveMutation.mutate({ id: r.id, action: 'complete' })
                  }}>
                  Erase account
                </button>
              </div>
            </div>
          )
        })
      }
    </div>
  )
}

/** Every account, with its subscription state and admin controls. */
function UsersCard({ currentUserId }) {
  const qc = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users'],
    queryFn: () => apiFetch('/api/admin/users'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => apiFetch(`/api/admin/users/${id}`, { method: 'DELETE' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin-users'] }); toast.success('Account deleted.') },
    onError: (e) => toast.error(e.message),
  })

  const roleMutation = useMutation({
    mutationFn: ({ id, role }) => apiFetch(`/api/admin/users/${id}/role`, { method: 'PUT', body: JSON.stringify({ role }) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['admin-users'] }); toast.success('Role updated.') },
    onError: (e) => toast.error(e.message),
  })

  const compMutation = useMutation({
    mutationFn: ({ id, days, reason }) => apiFetch(
      `/api/admin/users/${id}/subscription/grant`,
      { method: 'POST', body: JSON.stringify({ days, reason }) },
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] })
      toast.success('Complimentary access granted.')
    },
    onError: (e) => toast.error(e.message),
  })

  const revokeMutation = useMutation({
    mutationFn: (id) => apiFetch(`/api/admin/users/${id}/subscription/revoke`,
      { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-users'] })
      toast.success('Complimentary access withdrawn.')
    },
    // A refusal (live Stripe subscription) explains where to go instead, so
    // keep it on screen long enough to read.
    onError: (e) => toast.error(e.message, { duration: 10000 }),
  })

  /** Ask for a duration and reason, then comp the account. */
  function promptComp(u) {
    const raw = window.prompt(
      `Grant ${u.email} complimentary access.\n\n` +
      'How many days? Leave blank for no end date.', '365')
    if (raw === null) return
    const days = raw.trim() === '' ? null : Number(raw.trim())
    if (days !== null && (!Number.isInteger(days) || days < 1)) {
      toast.error('Enter a whole number of days, or leave it blank.')
      return
    }
    const reason = window.prompt(
      'Reason (shown in this list, for your own records):', '') || ''
    compMutation.mutate({ id: u.id, days, reason })
  }

  if (isLoading) return <Spinner />

  const users = data?.users ?? []
  const entitlements = data?.entitlements ?? {}

  return (
    <div className="card">
      <h2>Users ({users.length})</h2>
      {users.length === 0
        ? <div className="empty">No users found.</div>
        : users.map(u => {
          const ent = entitlements[u.id]
          const isSelf = u.id === currentUserId
          return (
            <div key={u.id} className="user-table-row">
              <div className="user-avatar" style={{ flexShrink: 0 }}>{u.email[0].toUpperCase()}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {u.email}
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 3, display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  {u.fighter_id && (
                    <>
                      <span style={{ textTransform: 'capitalize' }}>{u.fighter_sport}</span>
                      <span style={{
                        background: 'rgba(124,58,237,.15)', border: '1px solid rgba(124,58,237,.3)',
                        color: 'var(--accent-light)', borderRadius: 4, padding: '1px 6px',
                        fontWeight: 600, letterSpacing: '.03em', cursor: 'pointer', userSelect: 'all',
                      }}
                        title="Fighter ID — share with fighter to link their account">
                        ID {u.fighter_id}
                      </span>
                    </>
                  )}
                  <SubPill ent={ent} />
                  {ent?.comp_reason && (
                    <span style={{ color: 'var(--muted-2)' }}>{ent.comp_reason}</span>
                  )}
                </div>
              </div>

              {/* Comp / Revoke (admins never pay, so neither applies to them). */}
              {u.role !== 'admin' && (
                ent?.state === 'comped'
                  ? (
                    <button className="btn btn-sm" style={{ flexShrink: 0 }}
                      disabled={revokeMutation.isPending}
                      onClick={() => {
                        if (window.confirm(
                          `Withdraw complimentary access from ${u.email}?\n\n` +
                          'They drop to read-only unless they subscribe.'))
                          revokeMutation.mutate(u.id)
                      }}>
                      Revoke
                    </button>
                  )
                  : (
                    <button className="btn btn-sm" style={{ flexShrink: 0 }}
                      disabled={compMutation.isPending}
                      onClick={() => promptComp(u)}>
                      Comp
                    </button>
                  )
              )}
              <select
                value={u.role}
                disabled={isSelf}
                onChange={e => roleMutation.mutate({ id: u.id, role: e.target.value })}
                style={{
                  width: 120, flexShrink: 0,
                  background: 'var(--surface)', color: roleColour[u.role],
                  border: '1px solid var(--border)', borderRadius: 4, padding: '5px 8px',
                  fontSize: 12, cursor: isSelf ? 'not-allowed' : 'pointer',
                }}>
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
              {!isSelf ? (
                <button
                  className="btn btn-danger btn-sm"
                  style={{ flexShrink: 0 }}
                  disabled={deleteMutation.isPending}
                  onClick={() => {
                    if (window.confirm(`Delete ${u.email}? This cannot be undone.`))
                      deleteMutation.mutate(u.id)
                  }}>
                  Delete
                </button>
              ) : (
                // Placeholder the width of the Delete button, to keep rows aligned.
                <div style={{ width: 68, flexShrink: 0 }} />
              )}
            </div>
          )
        })
      }
    </div>
  )
}

/** The last 50 Stripe webhook deliveries, so "I paid and nothing happened"
 *  can be traced to an event id. */
function WebhookEventsCard() {
  const { data: eventData } = useQuery({
    queryKey: ['admin-billing-events'],
    queryFn: () => apiFetch('/api/admin/billing/events'),
  })
  const events = eventData?.events ?? []

  return (
    <div className="card">
      <h2>Stripe webhook events</h2>
      <p className="card-lead">
        The last 50 deliveries. <strong>failed</strong> means a payment was
        taken but could not be applied — Stripe retries for three days, and
        the event id here is what to search for in the Stripe dashboard.
      </p>
      {events.length === 0
        ? <div className="empty">No webhook events recorded.</div>
        : events.map(e => (
          <div key={e.id} className="history-row">
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500 }}>{e.event_type}</div>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2,
                            overflow: 'hidden', textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap' }}>
                {new Date(e.received_at).toLocaleString('en-GB')}
                {' · '}
                <span style={{ userSelect: 'all' }}>{e.stripe_event_id}</span>
              </div>
              {e.error && (
                <div style={{ fontSize: 11, color: 'var(--danger)', marginTop: 3 }}>
                  {e.error}
                </div>
              )}
            </div>
            <span className={`sub-pill ${WEBHOOK_PILL[e.status] ?? 'sub-pill--trialing'}`}>
              {e.status}
            </span>
          </div>
        ))
      }
    </div>
  )
}
