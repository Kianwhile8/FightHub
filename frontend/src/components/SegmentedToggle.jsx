/**
 * A small set of mutually exclusive choices, shown all at once.
 *
 * Used where a <select> would hide two options behind a click: three choices
 * fit on one line, and seeing them is faster than opening a menu to find out
 * what they are. Sized to sit level with `.filter-select` so it can stand in a
 * toolbar next to the dropdown filters without breaking the row.
 *
 * Buttons rather than radios, with aria-pressed: the control is not part of a
 * form submission anywhere it is currently used — callers hold the value in
 * state — and a radio group would need a name unique to each instance.
 */
export default function SegmentedToggle({ options, value, onChange, label, name }) {
  return (
    <div className="seg-toggle" role="group" aria-label={label}>
      {options.map(opt => (
        <button
          key={opt.value || '_all'}
          type="button"
          className={`seg-toggle-btn${value === opt.value ? ' active' : ''}`}
          aria-pressed={value === opt.value}
          onClick={() => onChange(opt.value)}
        >
          {opt.label}
        </button>
      ))}
      {/* Present only when the caller wants the value to travel with a native
          form submit; harmless otherwise. */}
      {name && <input type="hidden" name={name} value={value ?? ''} readOnly />}
    </div>
  )
}
