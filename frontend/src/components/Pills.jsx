// Small inline badges used across the fighter, gym, rankings and event pages.
// Keeping them here means each one looks and behaves the same everywhere.

import { SPORT_LABEL } from '../constants/sports'

/** "#3" next to a top-ranked fighter's name. Gold styling for the podium. */
export function RankPill({ rank, sport }) {
  if (!rank) return null
  return (
    <span className={`rank-pill${rank <= 3 ? ' rank-pill--podium' : ''}`}
      title={`Ranked #${rank} in ${SPORT_LABEL[sport] ?? sport}`}>
      #{rank}
    </span>
  )
}

/** Elo band ("Amateur", "Prospect", ...). Colour comes from `.band-<name>`. */
export function BandPill({ band }) {
  if (!band) return null
  const cls = `band-${band.toLowerCase().replace(/\s+/g, '-')}`
  return <span className={`band-pill ${cls}`}>{band}</span>
}

/** Rounded Elo rating, green when >= 0 and red when negative. */
export function EloPill({ elo }) {
  const value = elo ?? 0
  return (
    <span className={`elo-pill ${value >= 0 ? 'elo-positive' : 'elo-negative'}`}>
      {Math.round(value)}
    </span>
  )
}

// Muay Thai shares kickboxing's colour; there is no separate badge style.
const SPORT_BADGE = {
  mma: 'badge-mma', boxing: 'badge-box', kickboxing: 'badge-kb', muaythai: 'badge-kb',
}

/** Coloured sport label, e.g. on gym rosters and event cards. */
export function SportBadge({ sport }) {
  return (
    <span className={`badge ${SPORT_BADGE[sport] ?? ''}`}>
      {SPORT_LABEL[sport] ?? sport}
    </span>
  )
}

/** Amber "A-Class" style tag for a bout's ruleset. */
export function RulesetPill({ ruleset }) {
  if (!ruleset) return null
  return (
    <span style={{
      fontSize: 11, fontWeight: 600, padding: '2px 7px',
      background: 'rgba(251,191,36,.1)', border: '1px solid rgba(251,191,36,.3)',
      color: 'var(--warn)', borderRadius: 4,
    }}>{ruleset}</span>
  )
}
