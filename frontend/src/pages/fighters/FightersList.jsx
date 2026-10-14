import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient, keepPreviousData } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch } from '../../api/client'
import { useAuthStore } from '../../store/auth'
import { ENGLISH_COUNTIES } from '../../constants/counties'
import Spinner from '../../components/Spinner'
import SportTabs from '../../components/SportTabs'
import SegmentedToggle from '../../components/SegmentedToggle'
import PaywallGate from '../../components/PaywallGate'
import { useEntitlement } from '../../hooks/useEntitlement'
import { SPORT_LABEL } from '../../constants/sports'
import { WEIGHT_STEPS, weightLabel } from '../../constants/weights'
import {
  FIGHTER_GENDER_OPTIONS, GENDER_FILTER_OPTIONS, genderLabel,
} from '../../constants/gender'

const wordCount = (t) => t ? t.trim().split(/\s+/).filter(Boolean).length : 0

export default function FightersList() {
  const { sport } = useParams()
  const navigate  = useNavigate()
  const { user }  = useAuthStore()
  const { canWrite } = useEntitlement()
  const qc = useQueryClient()
  const [q, setQ]           = useState('')
  // What the user has typed vs. what has been asked of the server. Firing a
  // request per keystroke made the list flicker and hammered the API for
  // results nobody read.
  const [debouncedQ, setDebouncedQ] = useState('')
  const [county, setCounty] = useState('')
  const [maxWeight, setMaxWeight] = useState('')
  const [gender, setGender] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [descWords, setDescWords] = useState(0)

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 300)
    return () => clearTimeout(t)
  }, [q])

  // Whether this role could ever add a fighter, separate from whether the
  // account is currently entitled to. Keeping them apart is what lets the UI
  // show a coach a locked button (which they can act on by subscribing) while
  // showing a fighter nothing at all (which they cannot).
  const roleCanAdd = ['coach', 'admin'].includes(user?.role)
  const canAdd = roleCanAdd && canWrite

  // Seed the new-fighter form from the account's own answer where there is one
  // to use. 'undisclosed' deliberately does not carry over: the profile's
  // gender decides which division a fighter is matched in, so it has to be
  // stated rather than inherited from a refusal to state it.
  const defaultGender = FIGHTER_GENDER_OPTIONS
    .some(o => o.value === user?.gender) ? user.gender : ''

  // A coach sees only their own gyms here (the API filters by coach), so this
  // doubles as the list they are allowed to assign into.
  // ?mine=1 — the plain listing now returns every gym, and a coach may only
  // assign fighters into their own.
  const { data: gymsData } = useQuery({
    queryKey: ['gyms', 'mine'],
    queryFn: () => apiFetch('/api/gyms?mine=1'),
    enabled: canAdd,
  })
  const myGyms = gymsData?.gyms ?? []

  const params = new URLSearchParams()
  if (debouncedQ) params.set('q', debouncedQ)
  if (county)    params.set('county', county)
  if (maxWeight) params.set('max_weight', maxWeight)
  if (gender)    params.set('gender', gender)
  const qs = params.toString() ? `?${params}` : ''

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['fighters', sport, debouncedQ, county, maxWeight, gender],
    queryFn: () => apiFetch(`/api/${sport}/fighters${qs}`),
    // Hold the previous results on screen while the next set loads, instead of
    // dropping to an empty/loading state between every keystroke.
    placeholderData: keepPreviousData,
  })

  const addMutation = useMutation({
    mutationFn: (body) => apiFetch(`/api/${sport}/fighters`, { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: (f) => {
      qc.invalidateQueries({ queryKey: ['fighters', sport] })
      qc.invalidateQueries({ queryKey: ['stats'] })
      toast.success(`${f.name} added.`)
      setShowForm(false)
      setDescWords(0)
    },
    onError: (e) => toast.error(e.message),
  })

  function handleAdd(e) {
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
      gym_id:        fd.get('gym_id') ? +fd.get('gym_id') : null,
    })
    e.target.reset()
    setDescWords(0)
  }

  // Deliberately no early `return <Spinner />` here. Returning a spinner for
  // the whole page unmounted the toolbar — and with it the search input — so
  // every keystroke destroyed the field the user was typing into and the
  // caret jumped out. Only the results area below swaps to a spinner now.
  const fighters = data?.fighters ?? []

  return (
    <>
      <SportTabs title={`${SPORT_LABEL[sport] ?? sport} Fighters`} />

      <div className="toolbar">
        <div className="search-wrap">
          <svg className="search-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="6.5" cy="6.5" r="5"/><path d="m10.5 10.5 3.5 3.5"/>
          </svg>
          <input placeholder="Search fighters…" value={q}
            onChange={e => setQ(e.target.value)}
            autoComplete="off" />
          {isFetching && <span className="search-busy" aria-hidden="true" />}
        </div>
        <select className="filter-select" value={county} onChange={e => setCounty(e.target.value)}>
          <option value="">All counties</option>
          {ENGLISH_COUNTIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select className="filter-select" value={maxWeight}
          onChange={e => setMaxWeight(e.target.value)}>
          <option value="">Any weight</option>
          {WEIGHT_STEPS.map(w => (
            <option key={w} value={w}>{weightLabel(w)}</option>
          ))}
        </select>
        <SegmentedToggle
          label="Filter by gender"
          options={GENDER_FILTER_OPTIONS}
          value={gender}
          onChange={setGender}
        />
        {roleCanAdd && (
          <PaywallGate label="Subscribe to add fighters">
            <button className="btn btn-primary btn-sm" onClick={() => setShowForm(v => !v)}>
              {showForm ? 'Cancel' : '+ Add Fighter'}
            </button>
          </PaywallGate>
        )}
      </div>

      {showForm && (
        <div className="card">
          <h2>New Fighter</h2>
          <form onSubmit={handleAdd}>
            <div className="form-row-3">
              <div className="form-group">
                <label className="form-label">Name</label>
                <input name="name" required autoFocus />
              </div>
              <div className="form-group">
                <label className="form-label">Date of Birth</label>
                <input name="date_of_birth" type="date" max={new Date().toISOString().split('T')[0]} />
              </div>
              <div className="form-group">
                <label className="form-label">Weight (kg)</label>
                <input name="weight" type="number" step="0.1" min="40" required />
              </div>
            </div>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Gender</label>
                {/* Required: matchmaking will not pair fighters of
                    different genders, and a fighter with none recorded simply
                    never gets that protection. */}
                <select name="gender" className="select-input" required
                  defaultValue={defaultGender}>
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
            {myGyms.length > 0 && (
              <div className="form-group">
                <label className="form-label">Gym</label>
                {/* Defaulting to the coach's first gym is deliberate: a fighter
                    with no gym is one this coach cannot edit afterwards, since
                    that permission is derived from gym ownership. */}
                <select name="gym_id" className="select-input" defaultValue={myGyms[0].id}>
                  {myGyms.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}
                  <option value="">No gym (unattached)</option>
                </select>
              </div>
            )}
            <div className="form-group">
              <label className="form-label">Description</label>
              <textarea name="description" rows={3} placeholder="Optional fighter bio…"
                onInput={e => setDescWords(wordCount(e.target.value))}
                style={{ resize: 'vertical' }} />
              <div style={{ fontSize: 11, marginTop: 3,
                color: descWords > 200 ? 'var(--danger)' : 'var(--muted)' }}>
                {descWords} / 200 words
              </div>
            </div>
            <button type="submit" className="btn btn-primary btn-sm"
              disabled={addMutation.isPending || descWords > 200}>
              {addMutation.isPending ? 'Adding…' : 'Add Fighter'}
            </button>
          </form>
        </div>
      )}

      <div className="card" aria-busy={isFetching}>
        {isLoading
          ? <Spinner />
          : fighters.length === 0
          ? (
            <div className="empty">
              {q || county || maxWeight || gender
                ? 'No fighters match the current filters.'
                : 'No fighters registered yet.'}
              {(county || maxWeight || gender) && (
                <div style={{ marginTop: '.75rem' }}>
                  <button className="legal-jump"
                    onClick={() => { setCounty(''); setMaxWeight(''); setGender('') }}>
                    Clear filters
                  </button>
                </div>
              )}
            </div>
          )
          : fighters.map(f => (
            <div key={f.id} className="fighter-row" onClick={() => navigate(`/${sport}/fighters/${f.id}`)}>
              <div className="avatar">{f.name[0]}</div>
              <div className="fighter-info">
                <div className="fighter-name" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {f.name}
                  {f.rank && (
                    <span className={`rank-pill${f.rank <= 3 ? ' rank-pill--podium' : ''}`}
                      title={`Ranked #${f.rank} in ${SPORT_LABEL[sport] ?? sport}`}>
                      #{f.rank}
                    </span>
                  )}
                  {canAdd && (
                    // Spelled "ID 12", not "#12": a bare hash next to a name
                    // reads as a ranking, which is exactly what it is not.
                    <span className="id-pill"
                      title="Fighter ID — share with the fighter to link their account"
                      onClick={e => e.stopPropagation()}>
                      ID {f.id}
                    </span>
                  )}
                </div>
                <div className="fighter-meta">
                  {f.age != null ? `Age ${f.age}` : f.date_of_birth ? `DOB ${f.date_of_birth}` : 'Age unknown'} · {f.weight_kg}kg
                  {genderLabel(f.gender) && ` · ${genderLabel(f.gender)}`}
                  {f.county && ` · ${f.county}`}
                </div>
              </div>
              <span className="record-badge">
                {f.record_hidden ? '–' : `${f.wins ?? 0}W ${f.losses ?? 0}L ${f.draws ?? 0}D`}
              </span>
            </div>
          ))
        }
      </div>
    </>
  )
}
