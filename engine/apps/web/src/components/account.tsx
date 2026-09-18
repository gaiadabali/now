import Link from 'next/link'
import type { ReactNode } from 'react'

/**
 * Shared furniture for the reader account surface (E8.3, restyled S6 §4).
 *
 * Two families live here. `AccountShell` / `StatusBanner` / `Field` / `Submit`
 * are the narrow-column auth pages — register, sign in, verify, forgot,
 * reset — kept in one place so the wording of an error changes once, which
 * matters more than usual when several of those messages are deliberately
 * vague to avoid revealing whether an address has an account (see
 * `lib/readerActions.ts`). `Panel` / `EmptyState` are the dashboard's own
 * furniture: a panel is a rule and a label, never a card, and an empty panel
 * is an invitation rather than a blank — §4 is explicit that a reader must
 * not be able to tell "not built" from "you have none".
 *
 * Restyled onto `styles/account.css` rather than the pre-existing
 * `kicker`/`dek`/`meta`/`display`/`pullquote`/`signup__*` classes in
 * `base.css`/`magazine.css`: those two files are mid-migration to the S6
 * tokens as of this change (still `--ink-mute`, `--rule-hair`, `--t-dek`,
 * none of which `tokens.css` defines) and owned by other engineers working
 * this same tree. `.acct-btn`'s predecessor, `.signup__btn`, sets
 * `color: var(--ink-invert)` on a `var(--ink)` background — with
 * `--ink-invert` undefined that is invisible text, which is what this form
 * would have shipped. See `styles/account.css`'s header comment for the full
 * reasoning.
 */

export type Tone = 'ok' | 'bad' | 'info'

export type StatusMessage = { tone: Tone; head: string; body: string }

export function AccountShell({
  kicker,
  title,
  dek,
  status,
  children,
  footer,
}: {
  kicker: string
  title: string
  dek?: string
  status?: StatusMessage
  children?: ReactNode
  footer?: ReactNode
}) {
  return (
    <div className="shell acct-auth">
      <header>
        <p className="acct-auth__kicker">{kicker}</p>
        <h1 className="acct-auth__title">{title}</h1>
        {dek ? <p className="acct-auth__dek">{dek}</p> : null}
      </header>

      <div className="acct-auth__body">
        {status ? <StatusBanner status={status} /> : null}
        {children}
        {footer ? <p className="acct-auth__footer">{footer}</p> : null}
      </div>
    </div>
  )
}

export function StatusBanner({ status }: { status: StatusMessage }) {
  // `info` reads with the same red-edged treatment as no tone at all — it is
  // a prompt, not an outcome, so it does not earn `--ok` or `--warn`.
  const toneClass = status.tone === 'ok' ? 'acct-status--ok' : status.tone === 'bad' ? 'acct-status--bad' : ''
  return (
    <div
      className={`acct-status ${toneClass}`.trim()}
      // `alert` for failures so a screen reader announces it immediately —
      // the reader has just submitted and is waiting on the outcome.
      role={status.tone === 'bad' ? 'alert' : 'status'}
    >
      <p className="acct-status__head">{status.head}</p>
      <p className="acct-status__body">{status.body}</p>
    </div>
  )
}

export function Field({
  id,
  name,
  label,
  type = 'text',
  autoComplete,
  required,
  defaultValue,
  hint,
  minLength,
}: {
  id: string
  name: string
  label: string
  type?: string
  autoComplete?: string
  required?: boolean
  defaultValue?: string
  hint?: string
  minLength?: number
}) {
  return (
    <div className="acct-field">
      <label htmlFor={id} className="acct-field__label">
        {label}
      </label>
      <input
        className="acct-field__input"
        id={id}
        name={name}
        type={type}
        autoComplete={autoComplete}
        required={required}
        defaultValue={defaultValue}
        minLength={minLength}
      />
      {hint ? <span className="acct-field__hint">{hint}</span> : null}
    </div>
  )
}

export function Submit({ children }: { children: ReactNode }) {
  return (
    <button className="acct-btn" type="submit">
      {children}
    </button>
  )
}

/* --------------------------------------------------------------- dashboard */

/**
 * A dashboard panel — a `--edge` rule, a Bebas title, an optional
 * right-aligned action. Deliberately not a card: no border box, no shadow,
 * no radius (§4).
 */
export function Panel({
  title,
  action,
  children,
}: {
  title: string
  action?: { href: string; label: string }
  children: ReactNode
}) {
  return (
    <section className="acct-panel">
      <div className="acct-panel__head">
        <h2 className="acct-panel__title">{title}</h2>
        {action ? (
          <Link className="acct-panel__action" href={action.href}>
            {action.label}
          </Link>
        ) : null}
      </div>
      <div className="acct-panel__body">{children}</div>
    </section>
  )
}

/**
 * An empty panel's invitation — a dashed `--hair` box, one italic Cormorant
 * sentence, one Heebo micro line saying how to fill it (§4).
 *
 * Rendered for every panel with nothing to show, including the ones that are
 * not built yet (itineraries) and the ones that never will show anything
 * until a separate piece of work ships (reading history needs the beacon,
 * §4's own table). A reader cannot tell "not built" from "you have none" —
 * the copy is what teaches the feature either way, so it never says "coming
 * soon" without also saying what will make it fill.
 */
export function EmptyState({ lede, hint }: { lede: string; hint: ReactNode }) {
  return (
    <div className="acct-empty">
      <p className="acct-empty__lede">{lede}</p>
      <p className="acct-empty__hint">{hint}</p>
    </div>
  )
}
