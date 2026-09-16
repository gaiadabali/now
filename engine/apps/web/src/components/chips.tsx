import type { Option } from '@/lib/preferences'

/**
 * The picker's controls (E8.4).
 *
 * Checkboxes and radios, styled as chips — not a custom JavaScript widget.
 * §17 budgets the whole flow at 30 seconds, and the fastest thing that can
 * happen is the form working before any script has loaded. It also gets
 * keyboard navigation, screen-reader semantics and browser autofill for free,
 * which a div-with-onClick would each have to reimplement badly.
 *
 * The visual state is driven by `:checked` in CSS, so nothing here needs to
 * hydrate.
 */

export function ChipGroup({
  name,
  legend,
  hint,
  options,
  selected,
  single = false,
  allowNone = false,
}: {
  name: string
  legend: string
  hint?: string
  options: Option[]
  selected: string[]
  /** Radio rather than checkbox — one answer, like persona or budget. */
  single?: boolean
  /** Adds an explicit "no preference" radio. Only meaningful when `single`. */
  allowNone?: boolean
}) {
  if (options.length === 0) return null
  const chosen = new Set(selected)

  return (
    <fieldset className="chips" style={{ border: 0, padding: 0, margin: '0 0 var(--space-l)' }}>
      <legend className="kicker" style={{ marginBottom: 'var(--space-3xs)' }}>
        {legend}
      </legend>
      {hint ? (
        <p className="meta" style={{ margin: '0 0 var(--space-xs)', maxWidth: '46ch' }}>
          {hint}
        </p>
      ) : null}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3xs)' }}>
        {single && allowNone ? (
          <label className="chip">
            <input
              type="radio"
              name={name}
              value=""
              defaultChecked={selected.length === 0}
              className="chip__input"
            />
            <span className="chip__label">No preference</span>
          </label>
        ) : null}
        {options.map((option) => (
          <label className="chip" key={option.slug}>
            <input
              type={single ? 'radio' : 'checkbox'}
              name={name}
              value={option.slug}
              defaultChecked={chosen.has(option.slug)}
              className="chip__input"
            />
            <span className="chip__label">{option.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}
