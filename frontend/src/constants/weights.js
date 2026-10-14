// Weight filter steps, as upper bounds in kilograms.
//
// These follow the amateur boxing/kickboxing ladder, which is close enough to
// serve every discipline here. They are deliberately expressed as "at or under
// X kg" rather than named divisions: division names differ between sports and
// sanctioning bodies (a "featherweight" is not the same weight in boxing and
// MMA), so a name on a shared filter would be wrong for somebody. A number is
// wrong for nobody.
export const WEIGHT_STEPS = [48, 51, 54, 57, 60, 63.5, 67, 71, 75, 81, 86, 91]

/** "≤ 63.5 kg" — trims the trailing zero so it reads 57 rather than 57.0. */
export function weightLabel(kg) {
  return `≤ ${Number(kg)} kg`
}
