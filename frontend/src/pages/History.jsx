import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../api/client'
import Spinner from '../components/Spinner'
import SportTabs from '../components/SportTabs'
import { SPORT_LABEL } from '../constants/sports'
import { parseLocalDate } from '../utils/date'
import { RESULT_CLASS } from '../constants/fights'

// Every fight in one sport, grouped by month.

const MONTH_FMT = new Intl.DateTimeFormat('en-GB', { month: 'long', year: 'numeric' })

/**
 * Bucket fights into months, newest month first and newest fight first inside
 * each month.
 *
 * Fights with no usable date go into their own trailing group rather than being
 * dropped or silently sorted as epoch zero — a result recorded without a date
 * is still a result, and hiding it would make the page disagree with a
 * fighter's record.
 */
function groupByMonth(fights) {
  const groups = new Map()
  const undated = []

  for (const f of fights) {
    const d = parseLocalDate(f.date)
    if (!d) { undated.push(f); continue }
    // Key on year-month so ordering is lexicographic and collisions across
    // years are impossible.
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
    if (!groups.has(key)) groups.set(key, { key, label: MONTH_FMT.format(d), fights: [] })
    groups.get(key).fights.push(f)
  }

  const ordered = [...groups.values()].sort((a, b) => b.key.localeCompare(a.key))
  for (const g of ordered) {
    g.fights.sort((a, b) => parseLocalDate(b.date) - parseLocalDate(a.date))
  }
  if (undated.length) ordered.push({ key: 'undated', label: 'Date not recorded', fights: undated })
  return ordered
}

export default function History() {
  const { sport } = useParams()
  const navigate  = useNavigate()

  const { data, isLoading } = useQuery({
    queryKey: ['all-fights', sport],
    queryFn: () => apiFetch(`/api/${sport}/fights`),
  })

  const fights = data?.fights ?? []
  const months = groupByMonth(fights)

  return (
    <>
      <SportTabs title={`${SPORT_LABEL[sport] ?? sport} Fight History`} />

      {isLoading
        ? <Spinner />
        : fights.length === 0
          ? <div className="card"><div className="empty">No fights recorded yet.</div></div>
          : months.map(group => (
            <div key={group.key} className="card month-group">
              <div className="month-head">
                <h2 className="month-title">{group.label}</h2>
                <span className="month-count">
                  {group.fights.length} {group.fights.length === 1 ? 'fight' : 'fights'}
                </span>
              </div>

              {group.fights.map(f => (
                <div key={f.id} className="history-row">
                  <span className={RESULT_CLASS[f.result] ?? 'result-d'}>{f.result}</span>
                  <span className="history-fighter"
                    onClick={() => navigate(`/${sport}/fighters/${f.fighter_id}`)}>
                    {f.fighter}
                  </span>
                  <span style={{ color: 'var(--muted)', flexShrink: 0 }}>vs {f.opponent}</span>
                  {f.event && (
                    <span className="event-pill" title={`At ${f.event.name}`}
                      onClick={() => navigate(`/events/${f.event.id}`)}>
                      {f.event.name}
                    </span>
                  )}
                  <span style={{ color: 'var(--muted)', fontSize: 12, flexShrink: 0 }}>{f.method}</span>
                  {/* The month is the heading, so rows show only the day. */}
                  <span className="history-day">{dayLabel(f.date)}</span>
                </div>
              ))}
            </div>
          ))
      }
    </>
  )
}

/** "18 Sept" — the day within the month heading. */
function dayLabel(dateStr) {
  const d = parseLocalDate(dateStr)
  if (!d) return dateStr || '—'
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}
