// Fight vocabularies shared by the fighter page (logging a result) and the
// event page (completing a card bout).

/** Ruleset / class options, for the sports that grade bouts this way. */
export const RULESETS = {
  kickboxing: ['N-Class', 'C-Class', 'B-Class', 'A-Class', 'Pro-Amateur', 'Pro'],
  muaythai:   ['Novice', 'C-Class', 'B-Class', 'A-Class', 'Elite', 'Pro'],
}

/**
 * Win methods offered when recording a result. `value` is stored verbatim.
 *
 * NOTE: the matchmaker (app/services/matchmaker.py) weights methods by the
 * lower-cased values "ko", "tko", "submission", "decision" and
 * "disqualification". "KO/TKO" and "DQ" match none of those, so they are
 * currently scored as an ordinary decision-strength win.
 */
export const FIGHT_METHODS = [
  { value: 'Decision',   label: 'Decision' },
  { value: 'KO/TKO',     label: 'KO / TKO' },
  { value: 'Submission', label: 'Submission' },
  { value: 'DQ',         label: 'DQ' },
]

/** CSS class for a W / L / D result chip. */
export const RESULT_CLASS = { W: 'result-w', L: 'result-l', D: 'result-d' }
