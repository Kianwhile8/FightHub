// Single source of truth for the disciplines the UI offers. Must stay in step
// with VALID_SPORTS in app/constants.py and the ck_fighters_sport constraint in
// the database — a sport listed here but missing from either is a tab that
// loads and then fails on the first write.
export const SPORTS = ['mma', 'boxing', 'kickboxing', 'muaythai']

export const SPORT_LABEL = {
  mma: 'MMA',
  boxing: 'Boxing',
  kickboxing: 'Kickboxing',
  muaythai: 'Muay Thai',
}

// Remembers the discipline across pages that have no sport in their URL
// (Events, Gyms, Profile). Without it, visiting Events and coming back would
// silently drop a coach who works in Boxing onto the MMA pages.
const KEY = 'fighthub.sport'

export function lastSport() {
  try {
    const s = localStorage.getItem(KEY)
    return SPORTS.includes(s) ? s : 'mma'
  } catch {
    // Private browsing and blocked site data both throw here.
    return 'mma'
  }
}

export function rememberSport(sport) {
  try {
    if (SPORTS.includes(sport)) localStorage.setItem(KEY, sport)
  } catch { /* not worth surfacing — the default still works */ }
}
