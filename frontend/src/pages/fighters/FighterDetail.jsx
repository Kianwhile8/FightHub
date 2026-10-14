import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch } from '../../api/client'
import { useAuthStore } from '../../store/auth'
import Spinner from '../../components/Spinner'
import PaywallGate from '../../components/PaywallGate'
import { useEntitlement } from '../../hooks/useEntitlement'
import { FIGHTER_GENDER_OPTIONS, genderLabel } from '../../constants/gender'

const RESULT_CLASS = { W: 'result-w', L: 'result-l', D: 'result-d' }
const wordCount = (t) => t ? t.trim().split(/\s+/).filter(Boolean).length : 0

const RULESETS = {
  kickboxing: ['N-Class', 'C-Class', 'B-Class', 'A-Class', 'Pro-Amateur', 'Pro'],
  muaythai:   ['Novice', 'C-Class', 'B-Class', 'A-Class', 'Elite', 'Pro'],
}

export default function FighterDetail() {
  const { sport, id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { canWrite } = useEntitlement()
  const qc = useQueryClient()
  const [showFight, setShowFight]   = useState(false)
  const [editDesc, setEditDesc]     = useState(false)
  const [descWords, setDescWords]   = useState(0)
  const fid = +id

  // Role eligibility and current entitlement, kept apart: a coach out of
  // subscription sees a locked button they can act on, while a fighter sees
  // nothing, because subscribing would not give them this either.
  const roleCanManage = ['coach', 'promoter', 'admin'].includes(user?.role)
  const roleCanEdit   = ['coach', 'admin'].includes(user?.role)
  const canManage = roleCanManage && canWrite
  const canEdit   = roleCanEdit && canWrite

  const { data: fighter, isLoading } = useQuery({
    queryKey: ['fighter', sport, fid],
    queryFn: () => apiFetch(`/api/${sport}/fighters/${fid}`),
  })

  const { data: histData } = useQuery({
    queryKey: ['fighter-history', sport, fid],
    queryFn: () => apiFetch(`/api/${sport}/fighters/${fid}/fights`),
    enabled: !!fighter,
  })

  const addFightMutation = useMutation({
    mutationFn: (body) => apiFetch(`/api/${sport}/fighters/${fid}/fights`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fighter', sport, fid] })
      qc.invalidateQueries({ queryKey: ['fighter-history', sport, fid] })
      qc.invalidateQueries({ queryKey: ['all-fights', sport] })
      qc.invalidateQueries({ queryKey: ['rankings', sport] })
      toast.success('Fight recorded.')
      setShowFight(false)
    },
    onError: (e) => toast.error(e.message),
  })

  const updateMutation = useMutation({
    mutationFn: (body) => apiFetch(`/api/${sport}/fighters/${fid}`, { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fighter', sport, fid] })
      toast.success('Updated.')
      setEditDesc(false)
    },
    onError: (e) => toast.error(e.message),
  })

  const deleteMutation = useMutation({
    mutationFn: () => apiFetch(`/api/${sport}/fighters/${fid}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['fighters', sport] })
      qc.invalidateQueries({ queryKey: ['stats'] })
      toast.success('Fighter deleted.')
      navigate(`/${sport}/fighters`)
    },
    onError: (e) => toast.error(e.message),
  })

  function handleFight(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    addFightMutation.mutate({
      opponent_name: fd.get('opponent_name').trim(),
      result: fd.get('result'),
      method: fd.get('method') || 'Decision',
      date: fd.get('date') || undefined,
      ruleset: fd.get('ruleset') || null,
    })
    e.target.reset()
  }

  function handleEditDesc(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    const desc = fd.get('description').trim()
    if (wordCount(desc) > 200) { toast.error('Description must be 200 words or fewer.'); return }
    updateMutation.mutate({ description: desc || null })
  }

  if (isLoading) return <Spinner />
  if (!fighter)  return <div className="empty">Fighter not found.</div>

  const fights = histData?.fights ?? []

  return (
    <>
      <button className="back-btn" onClick={() => navigate(`/${sport}/fighters`)}>← Back to fighters</button>

      <div className="card">
        <div className="detail-header">
          <div className="detail-avatar">{fighter.name[0]}</div>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: '.25rem' }}>
              <h1 style={{ margin: 0 }}>{fighter.name}</h1>
              {fighter.elo_band && (
                <span className={`band-pill band-${fighter.elo_band.toLowerCase().replace(/\s+/g, '-')}`}>
                  {fighter.elo_band}
                </span>
              )}
              {fighter.elo !== undefined && (
                <span className={`elo-pill ${(fighter.elo ?? 0) >= 0 ? 'elo-positive' : 'elo-negative'}`}>
                  {Math.round(fighter.elo)}
                </span>
              )}
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
              <span style={{ fontSize: 12, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '.05em' }}>{sport}</span>
              {fighter.county && (
                <span style={{ fontSize: 12, color: 'var(--muted)' }}>· {fighter.county}</span>
              )}
              {fighter.gender
                ? <span className="gender-pill">{genderLabel(fighter.gender)}</span>
                : canEdit && (
                  // Fighters created before the field existed have no gender
                  // recorded, and without one they are never protected from a
                  // mixed pairing — so this is offered inline rather than
                  // buried in an edit form.
                  <select
                    className="gender-set"
                    defaultValue=""
                    disabled={updateMutation.isPending}
                    onChange={e => e.target.value && updateMutation.mutate({ gender: e.target.value })}
                  >
                    <option value="" disabled>Set gender…</option>
                    {FIGHTER_GENDER_OPTIONS.map(o => (
                      <option key={o.value} value={o.value}>{o.label}</option>
                    ))}
                  </select>
                )}
            </div>
          </div>
        </div>

        <div className="detail-grid">
          <div className="stat">
            <div className="stat-val">{fighter.age ?? '–'}</div>
            <div className="stat-lbl">Age</div>
          </div>
          {fighter.date_of_birth && (
            <div className="stat">
              <div className="stat-val" style={{ fontSize: 13 }}>{fighter.date_of_birth}</div>
              <div className="stat-lbl">Date of Birth</div>
            </div>
          )}
          <div className="stat"><div className="stat-val">{fighter.weight_kg}kg</div><div className="stat-lbl">Weight</div></div>
          <div className="stat">
            <div className="stat-val" style={{ color: 'var(--success)' }}>{fighter.record_hidden ? '–' : (fighter.wins ?? 0)}</div>
            <div className="stat-lbl">Wins</div>
          </div>
          <div className="stat">
            <div className="stat-val" style={{ color: 'var(--danger)' }}>{fighter.record_hidden ? '–' : (fighter.losses ?? 0)}</div>
            <div className="stat-lbl">Losses</div>
          </div>
        </div>

        <div className="btn-row">
          {roleCanManage && (
            <PaywallGate label="Subscribe to matchmake">
              <button className="btn btn-sm" onClick={() => navigate(`/${sport}/fighters/${fid}/matchmake`)}>
                Find Opponents
              </button>
            </PaywallGate>
          )}
          {roleCanManage && (
            <PaywallGate label="Subscribe to log fights">
              <button className="btn btn-primary btn-sm" onClick={() => setShowFight(v => !v)}>
                {showFight ? 'Cancel' : 'Log Fight'}
              </button>
            </PaywallGate>
          )}
          {canEdit && (
            <button className="btn btn-danger btn-sm"
              onClick={() => { if (window.confirm(`Delete ${fighter.name}? This cannot be undone.`)) deleteMutation.mutate() }}>
              Delete Fighter
            </button>
          )}
        </div>

        {showFight && (
          <>
            <hr className="divider" />
            <h2>Log Fight</h2>
            <form onSubmit={handleFight}>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Opponent name</label>
                  <input name="opponent_name" required autoFocus />
                </div>
                <div className="form-group">
                  <label className="form-label">Date</label>
                  <input name="date" type="date" />
                </div>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Result</label>
                  <select name="result" required defaultValue="">
                    <option value="" disabled>Select…</option>
                    <option value="W">Win</option>
                    <option value="L">Loss</option>
                    <option value="D">Draw</option>
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">Method</label>
                  <select name="method">
                    <option value="Decision">Decision</option>
                    <option value="KO/TKO">KO / TKO</option>
                    <option value="Submission">Submission</option>
                    <option value="DQ">DQ</option>
                  </select>
                </div>
              </div>
              {RULESETS[sport] && (
                <div className="form-group">
                  <label className="form-label">Ruleset / Class</label>
                  <select name="ruleset" defaultValue="">
                    <option value="">Not specified</option>
                    {RULESETS[sport].map(r => <option key={r} value={r}>{r}</option>)}
                  </select>
                </div>
              )}
              <button type="submit" className="btn btn-primary btn-sm" disabled={addFightMutation.isPending}>
                {addFightMutation.isPending ? 'Saving…' : 'Save Fight'}
              </button>
            </form>
          </>
        )}
      </div>

      {/* Description */}
      {(fighter.description || canEdit) && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '.5rem' }}>
            <h2 style={{ margin: 0 }}>Fighter Bio</h2>
            {canEdit && (
              <button className="btn btn-sm" onClick={() => { setEditDesc(v => !v); setDescWords(wordCount(fighter.description || '')) }}>
                {editDesc ? 'Cancel' : (fighter.description ? 'Edit' : '+ Add Bio')}
              </button>
            )}
          </div>
          {editDesc ? (
            <form onSubmit={handleEditDesc}>
              <div className="form-group">
                <textarea name="description" rows={4} defaultValue={fighter.description || ''}
                  onInput={e => setDescWords(wordCount(e.target.value))}
                  style={{ resize: 'vertical' }} autoFocus />
                <div style={{ fontSize: 11, marginTop: 3,
                  color: descWords > 200 ? 'var(--danger)' : 'var(--muted)' }}>
                  {descWords} / 200 words
                </div>
              </div>
              <button type="submit" className="btn btn-primary btn-sm"
                disabled={updateMutation.isPending || descWords > 200}>
                {updateMutation.isPending ? 'Saving…' : 'Save Bio'}
              </button>
            </form>
          ) : (
            <div style={{ fontSize: 14, lineHeight: 1.6,
              color: fighter.description ? 'inherit' : 'var(--muted)' }}>
              {fighter.description || 'No bio yet.'}
            </div>
          )}
        </div>
      )}

      <div className="card">
        <h2>Fight History</h2>
        {fighter.record_hidden
          ? <div className="empty">Record is hidden by this fighter.</div>
          : fights.length === 0
            ? <div className="empty">No fights recorded yet.</div>
            : fights.map(f => (
              <div key={f.id} className="history-row">
                <span className={RESULT_CLASS[f.result] ?? 'result-d'}>{f.result}</span>
                <span style={{ flex: 1 }}>vs {f.opponent}</span>
                {f.event && (
                  <span className="event-pill" title={`At ${f.event.name}`}
                    onClick={() => navigate(`/events/${f.event.id}`)}>
                    {f.event.name}
                  </span>
                )}
                {f.ruleset && (
                  <span style={{
                    fontSize: 11, fontWeight: 600, padding: '1px 6px',
                    background: 'rgba(251,191,36,.1)', border: '1px solid rgba(251,191,36,.3)',
                    color: 'var(--warn)', borderRadius: 4,
                  }}>{f.ruleset}</span>
                )}
                <span style={{ color: 'var(--muted)', fontSize: 12 }}>{f.method}</span>
                <span style={{ color: 'var(--muted)', fontSize: 12 }}>{f.date}</span>
              </div>
            ))
        }
      </div>
    </>
  )
}
