import type { ReactNode } from 'react'

/**
 * Shared furniture for the account pages (E8.3).
 *
 * Five pages — register, sign in, verify, forgot, reset — share one narrow
 * column and one status banner. Kept here rather than repeated so that the
 * wording of an error is changed in one place, which matters more than usual
 * when several of those messages are deliberately vague to avoid revealing
 * whether an address has an account.
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
    <div className="shell">
      <header className="band" style={{ paddingBottom: 0 }}>
        <p className="kicker kicker--red">{kicker}</p>
        <h1
          className="display display--light"
          style={{ fontSize: 'var(--t-display)', marginTop: 'var(--space-2xs)' }}
        >
          {title}
        </h1>
        {dek ? (
          <p className="dek" style={{ marginTop: 'var(--space-m)', maxWidth: '46ch' }}>
            {dek}
          </p>
        ) : null}
      </header>

      <section className="band">
        {status ? <StatusBanner status={status} /> : null}
        <div style={{ maxWidth: '34rem' }}>{children}</div>
        {footer ? (
          <div className="meta" style={{ marginTop: 'var(--space-l)', maxWidth: '46ch' }}>
            {footer}
          </div>
        ) : null}
      </section>
    </div>
  )
}

export function StatusBanner({ status }: { status: StatusMessage }) {
  return (
    <div
      className="pullquote"
      style={{
        marginBottom: 'var(--space-l)',
        borderLeftColor: status.tone === 'bad' ? undefined : 'var(--red)',
      }}
      // `alert` for failures so a screen reader announces it immediately —
      // the reader has just submitted and is waiting on the outcome.
      role={status.tone === 'bad' ? 'alert' : 'status'}
    >
      <p className="pullquote__text" style={{ fontSize: 'var(--t-card)' }}>
        {status.head}
      </p>
      <p className="meta" style={{ marginTop: 'var(--space-2xs)' }}>
        {status.body}
      </p>
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
    <p style={{ marginBottom: 'var(--space-m)' }}>
      <label
        htmlFor={id}
        className="kicker"
        style={{ display: 'block', marginBottom: 'var(--space-3xs)' }}
      >
        {label}
      </label>
      <input
        className="signup__input"
        style={{ width: '100%' }}
        id={id}
        name={name}
        type={type}
        autoComplete={autoComplete}
        required={required}
        defaultValue={defaultValue}
        minLength={minLength}
      />
      {hint ? (
        <span className="meta" style={{ display: 'block', marginTop: 'var(--space-3xs)' }}>
          {hint}
        </span>
      ) : null}
    </p>
  )
}

export function Submit({ children }: { children: ReactNode }) {
  return (
    <button className="signup__btn" type="submit" style={{ width: '100%' }}>
      {children}
    </button>
  )
}
