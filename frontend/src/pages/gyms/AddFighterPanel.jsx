import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch } from '../../api/client'
import { ENGLISH_COUNTIES } from '../../constants/counties'
import { SPORTS, SPORT_LABEL } from '../../constants/sports'
import { FIGHTER_GENDER_OPTIONS } from '../../constants/gender'

const wordCount = (t) => (t ? t.trim().split(/\s+/).filter(Boolean).length : 0)

/**
 * Adds fighters to a gym, either by creating them or by attaching an existing
 * unattached fighter.
 *
 * "New fighter" is the default tab deliberately. Early on there is nobody on
 * the platform to attach, so the search tab would open onto an empty list and
 * read as though the feature were broken.
 */
export default function AddFighterPanel({ gymId, onDone }) {
  const qc = useQueryClient()
  const [mode, setMode] = useState('new')

  function refresh() {
    qc.invalidateQueries({ queryKey: ['gym-fighters', gymId] })
    qc.invalidateQueries({ queryKey: ['gym-candidates', gymId] })
    qc.invalidateQueries({ queryKey: ['fighters'] })
    qc.invalidateQueries({ queryKey: ['stats'] })
  }

  return (
    <div className="card">
      <div className="auth-tabs" style={{ marginBottom: '1rem' }}>
        <button className={`auth-tab${mode === 'new' ? ' active' : ''}`} onClick={() => setMode('new')}>
          New fighter
        </button>
        <button className={`auth-tab${mode === 'existing' ? ' active' : ''}`} onClick={() => setMode('existing')}>
          Existing fighter
        </button>
      </div>

      {mode === 'new'
        ? <NewFighterForm gymId={gymId} onSaved={() => { refresh(); onDone?.() }} />
        : <ExistingFighterSearch gymId={gymId} onAdded={refresh} />}
    </div>
  )
}

function NewFighterForm({ gymId, onSaved }) {
  const [sport, setSport] = useState('mma')
  const [descWords, setDescWords] = useState(0)

  const addMutation = useMutation({
    // gym_id goes in the create call rather than a follow-up assignment, so a
    // fighter is never briefly gymless — that state is what locks a coach out
    // of editing their own fighter.
    mutationFn: (body) => apiFetch(`/api/${sport}/fighters`, {
      method: 'POST', body: JSON.stringify({ ...body, gym_id: gymId }),
    }),
    onSuccess: (f) => { toast.success(`${f.name} added to the gym.`); onSaved() },
    onError: (e) => toast.error(e.message),
  })

  function handleSubmit(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    const desc = fd.get('description').trim()
    if (wordCount(desc) > 200) { toast.error('Description must be 200 words or fewer.'); return }
    addMutation.mutate({
      name:          fd.get('name').trim(),
      date_of_birth: fd.get('date_of_birth') || null,
      weight:        +fd.get('weight'),
      gender:        fd.get('gender') || null,
      county:        fd.get('county') || null,
      description:   desc || null,
    })
  }

  return (
    <form onSubmit={handleSubmit}>
      <div className="form-row-3">
        <div className="form-group">
          <label className="form-label">Name</label>
          <input name="name" required autoFocus />
        </div>
        <div className="form-group">
          <label className="form-label">Discipline</label>
          <select value={sport} onChange={e => setSport(e.target.value)} className="select-input">
            {SPORTS.map(s => <option key={s} value={s}>{SPORT_LABEL[s] ?? s}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">Weight (kg)</label>
          <input name="weight" type="number" step="0.1" min="40" required />
        </div>
      </div>
      <div className="form-row-3">
        <div className="form-group">
          <label className="form-label">Date of Birth</label>
          <input name="date_of_birth" type="date" max={new Date().toISOString().split('T')[0]} />
        </div>
        <div className="form-group">
          <label className="form-label">Gender</label>
          <select name="gender" className="select-input" required defaultValue="">
            <option value="" disabled>Select…</option>
            {FIGHTER_GENDER_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <div className="form-group">
          <label className="form-label">County</label>
          <select name="county" className="select-input">
            <option value="">Not specified</option>
            {ENGLISH_COUNTIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>
      <div className="form-group">
        <label className="form-label">Description</label>
        <textarea name="description" rows={2} placeholder="Optional fighter bio…"
          onInput={e => setDescWords(wordCount(e.target.value))} style={{ resize: 'vertical' }} />
        <div style={{ fontSize: 11, marginTop: 3, color: descWords > 200 ? 'var(--danger)' : 'var(--muted)' }}>
          {descWords} / 200 words
        </div>
      </div>
      <button type="submit" className="btn btn-primary btn-sm"
        disabled={addMutation.isPending || descWords > 200}>
        {addMutation.isPending ? 'Adding…' : 'Add to gym'}
      </button>
    </form>
  )
}

function ExistingFighterSearch({ gymId, onAdded }) {
  const [q, setQ] = useState('')

  const { data, isFetching } = useQuery({
    queryKey: ['gym-candidates', gymId, q],
    queryFn: () => apiFetch(`/api/gyms/${gymId}/candidates?q=${encodeURIComponent(q)}`),
  })

  const assignMutation = useMutation({
    mutationFn: (f) => apiFetch(`/api/gyms/${gymId}/fighters/${f.id}?sport=${f.sport}`, { method: 'POST' }),
    onSuccess: (_, f) => { toast.success(`${f.name} added to the gym.`); onAdded() },
    onError: (e) => toast.error(e.message),
  })

  const candidates = data?.fighters ?? []

  return (
    <>
      <div className="search-wrap" style={{ marginBottom: '.9rem' }}>
        <svg className="search-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="6.5" cy="6.5" r="5" /><path d="m10.5 10.5 3.5 3.5" />
        </svg>
        <input placeholder="Search fighters by name…" value={q} onChange={e => setQ(e.target.value)} autoFocus />
      </div>

      {isFetching && candidates.length === 0
        ? <div className="empty">Searching…</div>
        : candidates.length === 0
          ? (
            <div className="empty">
              {q
                ? `No unattached fighters match “${q}”.`
                : 'No unattached fighters yet — use the New fighter tab to create one.'}
              <div style={{ fontSize: 12, marginTop: '.5rem', color: 'var(--muted-2)' }}>
                Fighters already training at another gym are not listed. Their
                current coach has to remove them first.
              </div>
            </div>
          )
          : candidates.map(f => (
            <div key={`${f.sport}-${f.id}`} className="gym-fighter-row">
              <div className="avatar" style={{ width: 32, height: 32, fontSize: 11 }}>{f.name[0]}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 500 }}>{f.name}</div>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>
                  {f.age != null ? `Age ${f.age}` : 'Age unknown'} · {f.weight_kg}kg
                  {f.county && ` · ${f.county}`} · ID {f.id}
                </div>
              </div>
              <span className="badge">{f.sport}</span>
              <button className="btn btn-sm" disabled={assignMutation.isPending}
                onClick={() => assignMutation.mutate(f)}>
                Add
              </button>
            </div>
          ))}
    </>
  )
}
