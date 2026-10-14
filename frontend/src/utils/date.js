/**
 * Date helpers for the ISO date strings ("2026-09-18") the API returns.
 *
 * `new Date('2026-09-18')` is parsed by the spec as UTC midnight, while
 * `new Date(2026, 8, 18)` and `today` are local. Mixing the two is a bug that
 * hides in the UK — where the offset is 0 or +1, so UTC midnight still falls on
 * the right local day — and appears west of Greenwich, where UTC midnight is
 * the previous local evening. The symptoms are an event dated today filed under
 * "previous", and a fight on the 1st grouped into the month before.
 *
 * Everything here therefore parses date-only strings as local dates.
 */

/** Parse "YYYY-MM-DD" as local midnight. Returns null if unparseable. */
export function parseLocalDate(value) {
  if (!value) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value))
  if (m) return new Date(+m[1], +m[2] - 1, +m[3])
  // Anything else (a full timestamp, or a format we don't recognise) falls back
  // to the platform parser rather than being discarded.
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Local midnight today, for comparing against parseLocalDate results. */
export function startOfToday() {
  const d = new Date()
  d.setHours(0, 0, 0, 0)
  return d
}
