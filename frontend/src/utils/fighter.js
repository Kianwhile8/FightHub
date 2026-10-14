// Small formatting helpers for fighter data from the API.

/**
 * "12W 3L 1D", or "–" when the fighter has hidden their record.
 * Pass `{ draws: false }` for the shorter "12W 3L".
 */
export function recordLabel(f, { draws = true } = {}) {
  if (f.record_hidden) return '–'
  const base = `${f.wins ?? 0}W ${f.losses ?? 0}L`
  return draws ? `${base} ${f.draws ?? 0}D` : base
}

/** Number of words in a free-text field (bios are capped at 200 words). */
export const wordCount = (text) =>
  text ? text.trim().split(/\s+/).filter(Boolean).length : 0

/** Max words in a fighter bio. Matches MAX_DESCRIPTION_WORDS on the server. */
export const MAX_BIO_WORDS = 200
