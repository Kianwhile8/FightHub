// Gender vocabulary, in one place so the browse filter, the fighter profile
// form and the sign-up form cannot drift apart.
//
// Three lists rather than one, because the three questions are not the same
// question:
//
//  * A fighter profile records the division a fighter competes in. Combat
//    sports are contested single-sex, so this is 'male' or 'female' and
//    nothing else — see migrations/…_fighter_gender.py. The database CHECK
//    constraint on fighters.gender enforces exactly these two.
//  * An account may decline to answer. 'undisclosed' is stored so that a
//    refusal is recorded as an answer rather than looking like a question that
//    was never put. Only users.gender accepts it.
//  * The filter adds "all", which is the absence of a filter, not a value.

/** Fighter profile — matches the fighters.gender CHECK constraint exactly. */
export const FIGHTER_GENDER_OPTIONS = [
  { value: 'male',   label: 'Male' },
  { value: 'female', label: 'Female' },
]

/** Registration — only ever shown to the fighter role. */
export const ACCOUNT_GENDER_OPTIONS = [
  ...FIGHTER_GENDER_OPTIONS,
  { value: 'undisclosed', label: 'Prefer not to say' },
]

/** Browse filter. '' is "no filter applied", consistent with the county and
 *  weight filters beside it. */
export const GENDER_FILTER_OPTIONS = [
  { value: '',       label: 'All' },
  ...FIGHTER_GENDER_OPTIONS,
]

const LABELS = {
  male: 'Male',
  female: 'Female',
  undisclosed: 'Not stated',
}

/** Display form of a stored value. Returns null for an unset gender so callers
 *  can omit the field entirely rather than printing "Unknown" at people. */
export function genderLabel(value) {
  return value ? (LABELS[value] ?? null) : null
}
