import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import Spinner from '../components/Spinner'
import SportTabs from '../components/SportTabs'
import { SPORTS, SPORT_LABEL } from '../constants/sports'
import { RankPill } from '../components/Pills'
import { recordLabel } from '../utils/fighter'

// The per-sport home page: fighter counts, plus the first few fighters.

export default function Dashboard() {
  const { sport } = useParams()
  const navigate  = useNavigate()

  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ['stats'],
    queryFn: () => apiFetch('/api/stats'),
    staleTime: 60_000,
  })

  const { data: fightersData, isLoading: fightersLoading } = useQuery({
    queryKey: ['fighters', sport, '', '', ''],
    queryFn: () => apiFetch(`/api/${sport}/fighters`),
  })

  const recent = (fightersData?.fighters ?? []).slice(0, 5)

  return (
    <>
      <SportTabs title="Dashboard" />

      {/* Each section renders as soon as its own query lands. */}
      <div className="stat-grid">
        <div className="stat stat--total">
          <div className="stat-val">{statsLoading ? '·' : stats?.total ?? '–'}</div>
          <div className="stat-lbl">Total Fighters</div>
        </div>
        {/* One tile per sport in SPORTS. */}
        {SPORTS.map(s => (
          <div key={s} className={`stat${s === sport ? ' stat--active' : ''}`}>
            <div className="stat-val">{statsLoading ? '·' : stats?.[s] ?? '–'}</div>
            <div className="stat-lbl">{SPORT_LABEL[s] ?? s}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>{SPORT_LABEL[sport] ?? sport} Fighters</h2>
        {fightersLoading
          ? <Spinner />
          : recent.length === 0
            ? <div className="empty">No fighters registered yet.</div>
            : (
              <>
                {recent.map(f => (
                  <div key={f.id} className="fighter-row"
                    onClick={() => navigate(`/${sport}/fighters/${f.id}`)}>
                    <div className="avatar">{f.name[0]}</div>
                    <div className="fighter-info">
                      <div className="fighter-name" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {f.name}
                        <RankPill rank={f.rank} sport={sport} />
                      </div>
                      <div className="fighter-meta">
                        {f.age != null ? `Age ${f.age}` : 'Age unknown'} · {f.weight_kg}kg
                      </div>
                    </div>
                    <span className="record-badge">
                      {recordLabel(f)}
                    </span>
                  </div>
                ))}
                {(fightersData?.fighters?.length ?? 0) > recent.length && (
                  <button className="row-more" onClick={() => navigate(`/${sport}/fighters`)}>
                    View all {fightersData.fighters.length} fighters →
                  </button>
                )}
              </>
            )
        }
      </div>
    </>
  )
}
