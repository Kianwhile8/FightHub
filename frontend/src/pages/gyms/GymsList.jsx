import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch } from '../../api/client'
import { useAuthStore } from '../../store/auth'
import { ENGLISH_COUNTIES } from '../../constants/counties'
import Spinner from '../../components/Spinner'
import PaywallGate from '../../components/PaywallGate'
import { useEntitlement } from '../../hooks/useEntitlement'

export default function GymsList() {
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { canWrite } = useEntitlement()
  const qc = useQueryClient()
  const [showForm, setShowForm]   = useState(false)
  const [county, setCounty]       = useState('')

  // Role eligibility and current entitlement, kept apart: a coach sees a
  // locked button they can act on; a fighter sees nothing, because there is
  // nothing they could do about it.
  const roleCanCreate = ['coach', 'admin'].includes(user?.role)
  const canCreate = roleCanCreate && canWrite

  const { data, isLoading } = useQuery({
    queryKey: ['gyms', county],
    queryFn: () => apiFetch(`/api/gyms${county ? `?county=${encodeURIComponent(county)}` : ''}`),
  })

  const createMutation = useMutation({
    mutationFn: (body) => apiFetch('/api/gyms', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['gyms'] })
      toast.success(`${d.gym.name} created.`)
      setShowForm(false)
    },
    onError: (e) => toast.error(e.message),
  })

  function handleCreate(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    createMutation.mutate({
      name:     fd.get('name').trim(),
      location: fd.get('location').trim(),
      county:   fd.get('county') || null,
    })
    e.target.reset()
  }

  if (isLoading) return <Spinner />

  const gyms = data?.gyms ?? []
  // A gym you coach is a thing you manage; every other gym is a thing you
  // browse. Splitting them means your own never scrolls out of reach once the
  // directory fills up, and it never appears twice.
  const myGyms    = gyms.filter(g => g.coach_id === user?.id)
  const otherGyms = gyms.filter(g => g.coach_id !== user?.id)

  return (
    <>
      <h1>Gyms</h1>
      <div className="toolbar">
        <select value={county} onChange={e => setCounty(e.target.value)}
          style={{ background: 'var(--surface)', color: 'var(--text)', border: '1px solid var(--border)',
                   borderRadius: 6, padding: '6px 10px', fontSize: 13 }}>
          <option value="">All counties</option>
          {ENGLISH_COUNTIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <div style={{ flex: 1 }} />
        {roleCanCreate && (
          <PaywallGate label="Subscribe to create a gym">
            <button className="btn btn-primary btn-sm" onClick={() => setShowForm(v => !v)}>
              {showForm ? 'Cancel' : '+ New Gym'}
            </button>
          </PaywallGate>
        )}
      </div>

      {showForm && (
        <div className="card">
          <h2>New Gym</h2>
          <form onSubmit={handleCreate}>
            <div className="form-row">
              <div className="form-group">
                <label className="form-label">Gym name</label>
                <input name="name" required autoFocus />
              </div>
              <div className="form-group">
                <label className="form-label">Location / address</label>
                <input name="location" />
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">County</label>
              <select name="county" style={{ background: 'var(--surface)', color: 'var(--text)',
                border: '1px solid var(--border)', borderRadius: 6, padding: '8px 10px', width: '100%', fontSize: 14 }}>
                <option value="">Not specified</option>
                {ENGLISH_COUNTIES.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <button type="submit" className="btn btn-primary btn-sm" disabled={createMutation.isPending}>
              {createMutation.isPending ? 'Creating…' : 'Create Gym'}
            </button>
          </form>
        </div>
      )}

      {myGyms.length > 0 && (
        <section className="gym-section">
          <h2 className="section-title">
            {myGyms.length === 1 ? 'My gym' : `My gyms (${myGyms.length})`}
          </h2>
          {myGyms.map(g => <GymCard key={g.id} gym={g} mine onOpen={() => navigate(`/gyms/${g.id}`)} />)}
        </section>
      )}

      <section className="gym-section">
        {myGyms.length > 0 && (
          <h2 className="section-title">
            {county ? `Other gyms in ${county}` : 'Other gyms'}
          </h2>
        )}
        {otherGyms.length === 0
          ? (
            <div className="empty">
              {gyms.length === 0
                ? (county ? `No gyms in ${county}.` : 'No gyms registered yet.')
                : (county ? `No other gyms in ${county}.` : 'No other gyms registered yet.')}
            </div>
          )
          : otherGyms.map(g => <GymCard key={g.id} gym={g} onOpen={() => navigate(`/gyms/${g.id}`)} />)
        }
      </section>
    </>
  )
}

function GymCard({ gym: g, mine, onOpen }) {
  return (
    <div className={`gym-card${mine ? ' gym-card--mine' : ''}`} onClick={onOpen}>
      <div className="gym-card-header">
        {g.photo
          ? <img src={`/uploads/${g.photo}`} alt={g.name}
              style={{ width: 44, height: 44, borderRadius: 8, objectFit: 'cover', flexShrink: 0 }} />
          : <div className="gym-icon">🏋️</div>
        }
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 15 }}>{g.name}</div>
          <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 2 }}>
            {[g.location, g.county].filter(Boolean).join(' · ') || 'No location set'}
          </div>
        </div>
      </div>
    </div>
  )
}
