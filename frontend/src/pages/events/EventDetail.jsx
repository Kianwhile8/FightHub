import { useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch, apiUpload } from '../../api/client'
import { useAuthStore } from '../../store/auth'
import Spinner from '../../components/Spinner'
import PaywallGate from '../../components/PaywallGate'
import { useEntitlement } from '../../hooks/useEntitlement'
import FightCardArranger from './FightCardArranger'

const SPORTS = ['mma', 'boxing', 'kickboxing', 'muaythai']
const SPORT_LABEL = { mma: 'MMA', boxing: 'Boxing', kickboxing: 'Kickboxing', muaythai: 'Muay Thai' }
const SPORT_BADGE = { mma: 'badge-mma', boxing: 'badge-box', kickboxing: 'badge-kb', muaythai: 'badge-kb' }

const RULESETS = {
  kickboxing: ['N-Class', 'C-Class', 'B-Class', 'A-Class', 'Pro-Amateur', 'Pro'],
  muaythai:   ['Novice', 'C-Class', 'B-Class', 'A-Class', 'Elite', 'Pro'],
}

export default function EventDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { canWrite } = useEntitlement()
  const qc = useQueryClient()
  const [boutSport, setBoutSport] = useState('mma')
  const [showBoutForm, setShowBoutForm] = useState(false)
  const [arranging, setArranging] = useState(false)
  const [showRegForm, setShowRegForm] = useState(false)
  const [completingId, setCompletingId] = useState(null)
  const photoRef = useRef(null)

  // Every write affordance on this page — the banner upload, adding bouts,
  // completing them, registering fighters, the card arranger — funnels through
  // canManage, so entitlement is ANDed in once here. The trial banner above the
  // page explains why they have gone.
  const roleCanManage = ['coach', 'promoter', 'admin'].includes(user?.role)
  const canManage  = roleCanManage && canWrite
  const isFighter  = user?.role === 'fighter'

  const { data: evData, isLoading } = useQuery({
    queryKey: ['event', id],
    queryFn: () => apiFetch(`/api/events/${id}`),
  })

  const { data: boutsData } = useQuery({
    queryKey: ['event-bouts', id],
    queryFn: () => apiFetch(`/api/events/${id}/bouts`),
  })

  const { data: regsData } = useQuery({
    queryKey: ['event-regs', id],
    queryFn: () => apiFetch(`/api/events/${id}/registrations`),
    enabled: !isFighter,
  })

  const { data: fightersData } = useQuery({
    queryKey: ['fighters', boutSport, ''],
    queryFn: () => apiFetch(`/api/${boutSport}/fighters`),
    enabled: showBoutForm || showRegForm,
  })

  const photoMutation = useMutation({
    mutationFn: (file) => apiUpload(`/api/upload/event/${id}`, file),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['event', id] }); toast.success('Photo updated.') },
    onError: (e) => toast.error(e.message),
  })

  const addBoutMutation = useMutation({
    mutationFn: (body) => apiFetch(`/api/events/${id}/bouts`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['event-bouts', id] }); toast.success('Bout added.'); setShowBoutForm(false) },
    onError: (e) => toast.error(e.message),
  })

  const deleteBoutMutation = useMutation({
    mutationFn: (boutId) => apiFetch(`/api/events/${id}/bouts/${boutId}`, { method: 'DELETE' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['event-bouts', id] }); toast.success('Bout removed.') },
    onError: (e) => toast.error(e.message),
  })

  const completeBoutMutation = useMutation({
    mutationFn: ({ boutId, ...body }) =>
      apiFetch(`/api/events/${id}/bouts/${boutId}/complete`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['event-bouts', id] })
      qc.invalidateQueries({ queryKey: ['all-fights'] })
      qc.invalidateQueries({ queryKey: ['fighter-history'] })
      qc.invalidateQueries({ queryKey: ['fighter'] })
      qc.invalidateQueries({ queryKey: ['rankings'] })
      toast.success('Bout complete — result added to both fighters, credited to this event.')
      setCompletingId(null)
    },
    onError: (e) => toast.error(e.message),
  })

  const orderMutation = useMutation({
    mutationFn: ({ order }) => apiFetch(`/api/events/${id}/bouts/order`, {
      method: 'PUT', body: JSON.stringify({ order }),
    }),
    onSuccess: (_, { done }) => {
      qc.invalidateQueries({ queryKey: ['event-bouts', id] })
      toast.success('Running order saved.')
      done?.()
    },
    onError: (e) => toast.error(e.message),
  })

  const registerMutation = useMutation({
    mutationFn: (body) => apiFetch(`/api/events/${id}/register`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['event-regs', id] }); toast.success('Fighter registered.'); setShowRegForm(false) },
    onError: (e) => toast.error(e.message),
  })

  function handleBout(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    addBoutMutation.mutate({
      sport: boutSport,
      fighter_a_id: +fd.get('fighter_a'),
      fighter_b_id: +fd.get('fighter_b'),
      ruleset: fd.get('ruleset') || null,
      description: fd.get('description')?.trim() || null,
    })
  }

  function handleComplete(e, bout) {
    e.preventDefault()
    const fd = new FormData(e.target)
    completeBoutMutation.mutate({
      boutId: bout.id,
      result: fd.get('result'),
      method: fd.get('method') || 'Decision',
      date:   fd.get('date') || undefined,
    })
  }

  function handleReg(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    registerMutation.mutate({ sport: boutSport, fighter_id: +fd.get('fighter_id') })
  }

  if (isLoading) return <Spinner />
  if (!evData?.event) return <div className="empty">Event not found.</div>

  const ev     = evData.event
  const bouts      = boutsData?.bouts ?? []
  const maxBouts   = boutsData?.max_bouts ?? null
  const canArrange = !!boutsData?.can_arrange
  const cardFull   = !!maxBouts && bouts.length >= maxBouts
  // The arrange phase opens only once the card is complete, which is the point
  // of setting a size at creation.
  const arrangeReady = canArrange && cardFull && bouts.length > 1
  const regs   = regsData?.registrations ?? []
  const fighters = fightersData?.fighters ?? []

  return (
    <>
      <button className="back-btn" onClick={() => navigate('/events')}>← Back to events</button>

      <div className="event-detail-banner" style={ev.photo ? {
        backgroundImage: `linear-gradient(rgba(0,0,0,.55), rgba(0,0,0,.7)), url(/uploads/${ev.photo})`,
        backgroundSize: 'cover', backgroundPosition: 'center',
      } : {}}>
        <h2>{ev.name}</h2>
        <div className="event-detail-meta">
          {ev.date && `${ev.date}${ev.time ? ` at ${ev.time}` : ''}`}
          {ev.venue_name && ` · ${ev.venue_name}`}
        </div>
        {ev.description && <div style={{ marginTop: '.5rem', fontSize: 14, opacity: .8 }}>{ev.description}</div>}
        {/* Role allows it, subscription does not — say so rather than leaving a
            promoter wondering where the fight-card controls went. */}
        {roleCanManage && !canWrite && (
          <div style={{ marginTop: '1rem' }}>
            <PaywallGate label="Subscribe to build this card" />
          </div>
        )}
        {canManage && (
          <div style={{ marginTop: '1rem' }}>
            <button className="btn btn-sm" style={{ opacity: .8, fontSize: 12 }}
              onClick={() => photoRef.current?.click()} disabled={photoMutation.isPending}>
              {photoMutation.isPending ? 'Uploading…' : (ev.photo ? '📷 Change Banner' : '📷 Add Banner Photo')}
            </button>
            <input ref={photoRef} type="file" accept="image/png,image/jpeg,image/webp"
              style={{ display: 'none' }} onChange={e => { if (e.target.files?.[0]) photoMutation.mutate(e.target.files[0]) }} />
          </div>
        )}
      </div>

      {/* Fight card */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.75rem' }}>
          <h2 style={{ margin: 0 }}>
            Fight Card ({bouts.length}{maxBouts ? ` / ${maxBouts}` : ''})
          </h2>
          <div style={{ display: 'flex', gap: '.5rem' }}>
            {arrangeReady && (
              <button className="btn btn-sm" onClick={() => setArranging(v => !v)}>
                {arranging ? 'Done arranging' : 'Arrange card'}
              </button>
            )}
            {canManage && !arranging && (
              <button className="btn btn-primary btn-sm"
                disabled={cardFull}
                title={cardFull ? `This card is full (${maxBouts} bouts).` : undefined}
                onClick={() => { setShowBoutForm(v => !v); setShowRegForm(false) }}>
                {showBoutForm ? 'Cancel' : '+ Add Bout'}
              </button>
            )}
          </div>
        </div>

        {maxBouts != null && (
          <div className="card-progress">
            <div className="card-progress-bar">
              <div className="card-progress-fill"
                style={{ width: `${Math.min(100, (bouts.length / maxBouts) * 100)}%` }} />
            </div>
            <div className="card-progress-text">
              {cardFull
                ? (canArrange
                  ? 'Card complete — you can now set the running order.'
                  : 'Card complete. The promoter who created this event sets the running order.')
                : `${maxBouts - bouts.length} more ${maxBouts - bouts.length === 1 ? 'bout' : 'bouts'} to complete the card.`}
            </div>
          </div>
        )}

        {showBoutForm && (
          <>
            <div className="chips" style={{ marginBottom: '.75rem' }}>
              {SPORTS.map(s => (
                <button key={s} className={`chip${boutSport === s ? ' active' : ''}`} onClick={() => setBoutSport(s)}>
                  {SPORT_LABEL[s] ?? s}
                </button>
              ))}
            </div>
            <form onSubmit={handleBout}>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Fighter A</label>
                  <select name="fighter_a" required defaultValue="">
                    <option value="" disabled>Select…</option>
                    {fighters.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Fighter B</label>
                  <select name="fighter_b" required defaultValue="">
                    <option value="" disabled>Select…</option>
                    {fighters.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </select>
                </div>
              </div>
              {RULESETS[boutSport] && (
                <div className="form-group">
                  <label className="form-label">Ruleset / Class</label>
                  <select name="ruleset" defaultValue="">
                    <option value="">Not specified</option>
                    {RULESETS[boutSport].map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
              )}
              <div className="form-group">
                <label className="form-label">Bout description (optional)</label>
                <textarea name="description" rows={2} placeholder="e.g. Title fight, catchweight agreement…"
                  style={{ resize: 'vertical' }} />
              </div>
              <button type="submit" className="btn btn-primary btn-sm" disabled={addBoutMutation.isPending}>
                {addBoutMutation.isPending ? 'Adding…' : 'Add Bout'}
              </button>
            </form>
            <hr className="divider" />
          </>
        )}

        {arranging
          ? (
            <FightCardArranger
              bouts={bouts}
              saving={orderMutation.isPending}
              onSave={(order, done) => orderMutation.mutate({ order, done })}
            />
          )
          : bouts.length === 0
          ? <div className="empty">No bouts on the card yet.</div>
          : bouts.map(b => (
            <div key={b.id} style={{ marginBottom: '.5rem' }}>
              <div className="bout-row">
                <div className="bout-fighter">{b.fighter_a?.name ?? '–'}</div>
                <div className="bout-vs">VS</div>
                <div className="bout-fighter" style={{ textAlign: 'right' }}>{b.fighter_b?.name ?? '–'}</div>
                <span className={`badge ${SPORT_BADGE[b.sport] ?? ''}`}>{SPORT_LABEL[b.sport] ?? b.sport}</span>
                {b.ruleset && (
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: '2px 7px',
                    background: 'rgba(251,191,36,.1)', border: '1px solid rgba(251,191,36,.3)',
                    color: 'var(--warn)', borderRadius: 4,
                  }}>{b.ruleset}</span>
                )}
                {b.completed ? (
                  <span className="bout-done" title={b.fight_date ? `Fought ${b.fight_date}` : undefined}>
                    ✓ {b.result === 'D' ? 'Draw' : `${b.winner?.name ?? 'Winner'} won`}
                    {b.method ? ` · ${b.method}` : ''}
                  </span>
                ) : canManage && (
                  <label style={{ display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0,
                    fontSize: 12, color: 'var(--muted)', cursor: 'pointer' }}>
                    <input type="checkbox" checked={completingId === b.id}
                      onChange={e => setCompletingId(e.target.checked ? b.id : null)}
                      style={{ width: 'auto', margin: 0, padding: 0, cursor: 'pointer' }} />
                    Complete
                  </label>
                )}
                {canManage && (
                  <button className="btn btn-danger btn-sm" style={{ padding: '3px 8px' }}
                    onClick={() => deleteBoutMutation.mutate(b.id)}>✕</button>
                )}
              </div>
              {b.description && (
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 4, paddingLeft: 4 }}>
                  {b.description}
                </div>
              )}
              {completingId === b.id && (
                <form onSubmit={e => handleComplete(e, b)} style={{ padding: '.75rem 0 .25rem' }}>
                  <div className="form-row-3">
                    <div className="form-group">
                      <label className="form-label">Winner</label>
                      <select name="result" required defaultValue="">
                        <option value="" disabled>Select…</option>
                        <option value="A">{b.fighter_a?.name ?? 'Fighter A'}</option>
                        <option value="B">{b.fighter_b?.name ?? 'Fighter B'}</option>
                        <option value="D">Draw</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Method</label>
                      <select name="method" defaultValue="Decision">
                        <option value="Decision">Decision</option>
                        <option value="KO/TKO">KO / TKO</option>
                        <option value="Submission">Submission</option>
                        <option value="DQ">DQ</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">Date</label>
                      <input name="date" type="date" defaultValue={ev.date || ''} />
                    </div>
                  </div>
                  <button type="submit" className="btn btn-primary btn-sm" disabled={completeBoutMutation.isPending}>
                    {completeBoutMutation.isPending ? 'Saving…' : 'Confirm Result'}
                  </button>
                </form>
              )}
            </div>
          ))
        }
      </div>

      {/* Registrations — hidden from fighters */}
      {!isFighter && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.75rem' }}>
            <h2 style={{ margin: 0 }}>Registrations ({regs.length})</h2>
            {canManage && (
              <button className="btn btn-sm" onClick={() => { setShowRegForm(v => !v); setShowBoutForm(false) }}>
                {showRegForm ? 'Cancel' : '+ Register Fighter'}
              </button>
            )}
          </div>

          {showRegForm && (
            <>
              <div className="chips" style={{ marginBottom: '.75rem' }}>
                {SPORTS.map(s => (
                  <button key={s} className={`chip${boutSport === s ? ' active' : ''}`} onClick={() => setBoutSport(s)}>
                    {SPORT_LABEL[s] ?? s}
                  </button>
                ))}
              </div>
              <form onSubmit={handleReg}>
                <div className="form-group">
                  <label className="form-label">Fighter</label>
                  <select name="fighter_id" required defaultValue="">
                    <option value="" disabled>Select…</option>
                    {fighters.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </select>
                </div>
                <button type="submit" className="btn btn-primary btn-sm" disabled={registerMutation.isPending}>
                  {registerMutation.isPending ? 'Registering…' : 'Register'}
                </button>
              </form>
              <hr className="divider" />
            </>
          )}

          {regs.length === 0
            ? <div className="empty">No fighters registered yet.</div>
            : regs.map(r => (
              <div key={r.id} className="gym-fighter-row">
                <div className="avatar" style={{ width: 32, height: 32, fontSize: 11 }}>{r.fighter?.name?.[0]}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500, fontSize: 13 }}>{r.fighter?.name}</div>
                </div>
                <span className={`badge ${SPORT_BADGE[r.sport] ?? ''}`}>{r.sport}</span>
              </div>
            ))
          }
        </div>
      )}
    </>
  )
}
