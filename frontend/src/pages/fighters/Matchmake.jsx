import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../api/client'
import Spinner from '../../components/Spinner'
import PaywallGate from '../../components/PaywallGate'
import { useEntitlement } from '../../hooks/useEntitlement'

export default function Matchmake() {
  const { sport, id } = useParams()
  const navigate = useNavigate()
  const { canWrite } = useEntitlement()

  const { data: fighter } = useQuery({
    queryKey: ['fighter', sport, +id],
    queryFn: () => apiFetch(`/api/${sport}/fighters/${id}`),
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['matches', sport, id],
    // The suggestions endpoint is paywalled, so there is no point spending a
    // request to be told so — the panel below explains it instead.
    enabled: canWrite,
    queryFn: () => apiFetch(`/api/${sport}/fighters/${id}/matches`),
    // A 402 is a settled answer, not a blip. Retrying it would just produce a
    // second 402 and a second error toast.
    retry: (count, err) => !err?.paymentRequired && count < 1,
  })

  if (canWrite && isLoading) return <Spinner />

  const matches = data?.matches ?? []
  // Opponents held back because the experience gap was too wide. Without this
  // note an unproven fighter just sees an empty list and no reason for it.
  const excluded = data?.excluded ?? 0

  function scoreClass(score) {
    if (score >= 70) return 'score-high'
    if (score >= 40) return 'score-mid'
    return 'score-low'
  }

  return (
    <>
      <button className="back-btn" onClick={() => navigate(`/${sport}/fighters/${id}`)}>← Back</button>
      <h1>Opponent Suggestions</h1>

      {fighter && (
        <div className="card" style={{ padding: '.75rem 1.25rem', marginBottom: '1rem' }}>
          <span style={{ fontSize: 14 }}>
            Matchmaking for <strong>{fighter.name}</strong> · {sport.toUpperCase()} · {fighter.weight_kg}kg
            {!fighter.record_hidden && ` · ${fighter.wins ?? 0}W ${fighter.losses ?? 0}L`}
          </span>
        </div>
      )}

      {/* The whole results panel, replaced. Matchmaking is what the paid tier
          is actually for, so this is the one place an upsell belongs in full
          rather than as a locked button. */}
      <PaywallGate
        mode="panel"
        title="Opponent suggestions need a subscription"
        body="Matchmaking scores every fighter in the discipline on weight, experience, activity and rating, and enforces same-sex pairing. It is the part of FightHub a subscription pays for. Browsing the database, the rankings and your own record stays free."
      >
      <div className="card">
        {error?.paymentRequired
          ? <div className="empty">{error.message}</div>
          : matches.length === 0
          ? (
            <div className="empty">
              {excluded > 0
                ? `No suitable opponents found. ${excluded} ${excluded === 1 ? 'fighter was' : 'fighters were'} held back as too experienced for this matchup.`
                : 'No suitable opponents found.'}
            </div>
          )
          : matches.map((m, i) => (
            <div key={m.fighter.id} className="match-card">
              <div className="rank-num">{i + 1}</div>
              <div className="match-info">
                <div className="match-names" style={{ cursor: 'pointer' }}
                  onClick={() => navigate(`/${sport}/fighters/${m.fighter.id}`)}>
                  {m.fighter.name}
                </div>
                <div className="match-meta">
                  {m.fighter.weight_kg}kg
                  {!m.fighter.record_hidden && ` · ${m.fighter.wins ?? 0}W ${m.fighter.losses ?? 0}L`}
                  {m.transferred_bouts > 0 &&
                    ` · +${m.transferred_bouts} bouts carried from other disciplines`}
                </div>
              </div>
              <span className={`match-score-pill ${scoreClass(m.score ?? 0)}`}>
                {Math.round(m.score ?? 0)}
              </span>
            </div>
          ))
        }
      </div>
      </PaywallGate>
    </>
  )
}
