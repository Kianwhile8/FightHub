import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import Spinner from '../components/Spinner'
import SportTabs from '../components/SportTabs'
import { SPORT_LABEL } from '../constants/sports'

function rankClass(rank) {
  if (rank === 1) return 'gold'
  if (rank === 2) return 'silver'
  if (rank === 3) return 'bronze'
  return ''
}

function bandClass(band) {
  return `band-${(band ?? 'amateur').toLowerCase().replace(/\s+/g, '-')}`
}

export default function Rankings() {
  const { sport } = useParams()
  const navigate  = useNavigate()

  const { data, isLoading } = useQuery({
    queryKey: ['rankings', sport],
    queryFn: () => apiFetch(`/api/${sport}/rankings`),
    staleTime: 60_000,
  })

  if (isLoading) return <Spinner />

  const rankings = data?.rankings ?? []

  return (
    <>
      <SportTabs title={`${SPORT_LABEL[sport] ?? sport} Rankings`} />
      <div className="card">
        {rankings.length === 0
          ? <div className="empty">No fighters to rank yet.</div>
          : rankings.map(f => (
            <div key={f.id} className="ranking-row" onClick={() => navigate(`/${sport}/fighters/${f.id}`)}>
              <div className={`rank-num ${rankClass(f.rank)}`}>{f.rank}</div>
              <div className="avatar" style={{ width: 32, height: 32, fontSize: 11 }}>{f.name[0]}</div>
              <div className="fighter-info">
                <div className="fighter-name">{f.name}</div>
                <div className="fighter-meta">
                  {f.record_hidden ? '–' : `${f.wins ?? 0}W ${f.losses ?? 0}L ${f.draws ?? 0}D`}
                  {f.weight_kg && ` · ${f.weight_kg}kg`}
                </div>
              </div>
              {f.elo_band && <span className={`band-pill ${bandClass(f.elo_band)}`}>{f.elo_band}</span>}
              <span className={`elo-pill ${(f.elo ?? 0) >= 0 ? 'elo-positive' : 'elo-negative'}`}>
                {Math.round(f.elo ?? 0)}
              </span>
            </div>
          ))
        }
      </div>
    </>
  )
}
