import { useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiFetch, apiUpload } from '../../api/client'
import { useAuthStore } from '../../store/auth'
import { ENGLISH_COUNTIES } from '../../constants/counties'
import Spinner from '../../components/Spinner'
import PaywallGate from '../../components/PaywallGate'
import { useEntitlement } from '../../hooks/useEntitlement'
import AddFighterPanel from './AddFighterPanel'

const SPORT_BADGE = { mma: 'badge-mma', boxing: 'badge-box', kickboxing: 'badge-kb' }

export default function GymDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuthStore()
  const { canWrite } = useEntitlement()
  const qc = useQueryClient()
  const gymId  = +id
  const photoRef = useRef(null)
  const [editGym, setEditGym] = useState(false)
  const [addingFighter, setAddingFighter] = useState(false)

  // Every write affordance on this page funnels through canManage, so ANDing
  // entitlement in here covers edit, delete, the photo upload and the roster
  // add/remove in one place. The banner at the top of the page says why they
  // have gone, and /billing says what to do about it.
  const roleCanManage = ['coach', 'admin'].includes(user?.role)
  const canManage = roleCanManage && canWrite

  const { data, isLoading } = useQuery({
    queryKey: ['gym', gymId],
    queryFn: () => apiFetch(`/api/gyms/${gymId}`),
  })

  const { data: fightersData, isLoading: fightersLoading } = useQuery({
    queryKey: ['gym-fighters', gymId],
    queryFn: () => apiFetch(`/api/gyms/${gymId}/fighters`),
    enabled: !!data,
  })

  const updateMutation = useMutation({
    mutationFn: (body) => apiFetch(`/api/gyms/${gymId}`, { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gym', gymId] })
      qc.invalidateQueries({ queryKey: ['gyms'] })
      toast.success('Gym updated.')
      setEditGym(false)
    },
    onError: (e) => toast.error(e.message),
  })

  const deleteMutation = useMutation({
    mutationFn: () => apiFetch(`/api/gyms/${gymId}`, { method: 'DELETE' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gyms'] })
      toast.success('Gym deleted.')
      navigate('/gyms')
    },
    onError: (e) => toast.error(e.message),
  })

  const removeMutation = useMutation({
    mutationFn: (f) => apiFetch(`/api/gyms/${gymId}/fighters/${f.id}?sport=${f.sport}`, { method: 'DELETE' }),
    onSuccess: (_, f) => {
      qc.invalidateQueries({ queryKey: ['gym-fighters', gymId] })
      qc.invalidateQueries({ queryKey: ['gym-candidates', gymId] })
      toast.success(`${f.name} removed from the gym.`)
    },
    onError: (e) => toast.error(e.message),
  })

  const photoMutation = useMutation({
    mutationFn: (file) => apiUpload(`/api/upload/gym/${gymId}`, file),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gym', gymId] })
      qc.invalidateQueries({ queryKey: ['gyms'] })
      toast.success('Photo updated.')
    },
    onError: (e) => toast.error(e.message),
  })

  function handleUpdate(e) {
    e.preventDefault()
    const fd = new FormData(e.target)
    updateMutation.mutate({
      name:     fd.get('name').trim(),
      location: fd.get('location').trim(),
      county:   fd.get('county') || null,
    })
  }

  if (isLoading) return <Spinner />
  if (!data?.gym) return <div className="empty">Gym not found.</div>

  const gym      = data.gym
  const fighters = fightersData?.fighters ?? []
  const photoUrl = gym.photo ? `/uploads/${gym.photo}` : null

  return (
    <>
      <button className="back-btn" onClick={() => navigate('/gyms')}>← Back to gyms</button>

      <div className="card">
        {photoUrl && (
          <img src={photoUrl} alt={gym.name}
            style={{ width: '100%', maxHeight: 200, objectFit: 'cover', borderRadius: 8, marginBottom: '1rem' }} />
        )}

        <div className="gym-card-header" style={{ marginBottom: '1rem' }}>
          {!photoUrl && <div className="gym-icon" style={{ width: 56, height: 56, fontSize: 24 }}>🏋️</div>}
          <div style={{ flex: 1 }}>
            <h1 style={{ marginBottom: '.2rem' }}>{gym.name}</h1>
            <div style={{ color: 'var(--muted)', fontSize: 13 }}>
              {[gym.location, gym.county].filter(Boolean).join(' · ') || 'No location set'}
            </div>
          </div>
        </div>

        {/* Shown when the role allows it but the subscription does not, so the
            controls are not just silently absent. */}
        {roleCanManage && !canWrite && (
          <div className="btn-row">
            <PaywallGate label="Subscribe to manage this gym" />
          </div>
        )}

        {canManage && (
          <div className="btn-row">
            <button className="btn btn-sm" onClick={() => photoRef.current?.click()} disabled={photoMutation.isPending}>
              {photoMutation.isPending ? 'Uploading…' : (photoUrl ? 'Change Photo' : '+ Add Photo')}
            </button>
            <input ref={photoRef} type="file" accept="image/png,image/jpeg,image/webp"
              style={{ display: 'none' }} onChange={e => { if (e.target.files?.[0]) photoMutation.mutate(e.target.files[0]) }} />

            <button className="btn btn-sm" onClick={() => setEditGym(v => !v)}>
              {editGym ? 'Cancel' : 'Edit Gym'}
            </button>
            <button className="btn btn-danger btn-sm"
              onClick={() => { if (window.confirm(`Delete ${gym.name}?`)) deleteMutation.mutate() }}>
              Delete Gym
            </button>
          </div>
        )}

        {editGym && (
          <>
            <hr className="divider" />
            <form onSubmit={handleUpdate}>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Gym name</label>
                  <input name="name" defaultValue={gym.name} required autoFocus />
                </div>
                <div className="form-group">
                  <label className="form-label">Location / address</label>
                  <input name="location" defaultValue={gym.location || ''} />
                </div>
              </div>
              <div className="form-group">
                <label className="form-label">County</label>
                <select name="county" defaultValue={gym.county || ''}
                  style={{ background: 'var(--surface)', color: 'var(--text)',
                    border: '1px solid var(--border)', borderRadius: 6, padding: '8px 10px', width: '100%', fontSize: 14 }}>
                  <option value="">Not specified</option>
                  {ENGLISH_COUNTIES.map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <button type="submit" className="btn btn-primary btn-sm" disabled={updateMutation.isPending}>
                {updateMutation.isPending ? 'Saving…' : 'Save Changes'}
              </button>
            </form>
          </>
        )}
      </div>

      {canManage && addingFighter && (
        <AddFighterPanel gymId={gymId} onDone={() => setAddingFighter(false)} />
      )}

      <div className="card">
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '.5rem' }}>
          <h2 style={{ margin: 0, flex: 1 }}>Fighters ({fighters.length})</h2>
          {canManage && (
            <button className="btn btn-primary btn-sm" onClick={() => setAddingFighter(v => !v)}>
              {addingFighter ? 'Cancel' : '+ Add Fighter'}
            </button>
          )}
        </div>
        {fightersLoading
          ? <Spinner />
          : fighters.length === 0
            ? (
              <div className="empty">
                No fighters in this gym.
                {canManage && !addingFighter && (
                  <div style={{ fontSize: 12, marginTop: '.5rem', color: 'var(--muted-2)' }}>
                    Use “+ Add Fighter” to create one or bring across an existing fighter.
                  </div>
                )}
              </div>
            )
            : fighters.map(f => (
              <div key={`${f.sport}-${f.id}`} className="gym-fighter-row"
                style={{ cursor: 'pointer' }}
                onClick={() => navigate(`/${f.sport}/fighters/${f.id}`)}>
                <div className="avatar" style={{ width: 32, height: 32, fontSize: 11 }}>{f.name[0]}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500, display: 'flex', alignItems: 'center', gap: 8 }}>
                    {f.name}
                    {f.rank && (
                      <span className={`rank-pill${f.rank <= 3 ? ' rank-pill--podium' : ''}`}
                        title={`Ranked #${f.rank} in ${f.sport}`}>
                        #{f.rank}
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1, display: 'flex', alignItems: 'center', gap: 6 }}>
                    {f.record_hidden ? '–' : `${f.wins ?? 0}W ${f.losses ?? 0}L`}
                    {f.county && ` · ${f.county}`}
                    <span className="id-pill"
                      title="Fighter ID — share with fighter to link their account"
                      onClick={e => e.stopPropagation()}>
                      ID {f.id}
                    </span>
                  </div>
                </div>
                <span className={`badge ${SPORT_BADGE[f.sport] ?? ''}`}>{f.sport}</span>
                {f.elo_band && <span className={`band-pill band-${(f.elo_band ?? 'amateur').toLowerCase().replace(' ', '-')}`}>{f.elo_band}</span>}
                {canManage && (
                  <button
                    className="btn btn-danger btn-sm"
                    disabled={removeMutation.isPending}
                    // The row navigates to the fighter; without this the click
                    // would remove them and then open the page of the fighter
                    // just removed.
                    onClick={e => {
                      e.stopPropagation()
                      if (window.confirm(`Remove ${f.name} from ${gym.name}? Their record and profile are kept — only the gym link is cleared.`)) {
                        removeMutation.mutate(f)
                      }
                    }}>
                    Remove
                  </button>
                )}
              </div>
            ))
        }
      </div>
    </>
  )
}
