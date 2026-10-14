import { useEffect } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { SPORTS, SPORT_LABEL, rememberSport } from '../constants/sports'

/**
 * Discipline switcher, rendered by each sport-scoped page rather than by the
 * shell.
 *
 * Living in the page is what keeps the control honest: it appears on Fighters,
 * Rankings, History and the Dashboard — the pages whose content is actually
 * per-discipline — and nowhere else. Events, Gyms, Profile and Admin span all
 * disciplines, so a switcher there changed a global-looking setting that those
 * pages then ignored.
 *
 * Pass `title` to render the page heading alongside it, so the reading order is
 * "Fighters · MMA" rather than a heading and an unattached row of buttons.
 */
export default function SportTabs({ title }) {
  const { sport = 'mma' } = useParams()
  const navigate = useNavigate()
  const location = useLocation()

  // Remembered so the sidebar links and any sport-less page can return you to
  // the discipline you were last working in.
  useEffect(() => { rememberSport(sport) }, [sport])

  function switchTo(s) {
    if (s === sport) return
    const segs = location.pathname.split('/')
    // Swap the sport segment in place, so switching discipline keeps you on
    // the same kind of page instead of bouncing you to a dashboard.
    if (SPORTS.includes(segs[1])) {
      segs[1] = s
      navigate(segs.join('/'))
    } else {
      navigate(`/${s}/dashboard`)
    }
  }

  return (
    <div className="page-head">
      {title && <h1 className="page-head-title">{title}</h1>}
      <div className="sport-switch" role="tablist" aria-label="Select discipline">
        {SPORTS.map(s => (
          <button
            key={s}
            role="tab"
            aria-selected={s === sport}
            className={`sport-switch-tab${s === sport ? ' active' : ''}`}
            onClick={() => switchTo(s)}
          >
            {SPORT_LABEL[s] ?? s}
          </button>
        ))}
      </div>
    </div>
  )
}
