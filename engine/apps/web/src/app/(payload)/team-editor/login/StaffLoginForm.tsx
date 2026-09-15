'use client'

import { useRouter } from 'next/navigation'
import { useState, type FormEvent } from 'react'

/**
 * The only client component in the admin path.
 *
 * `docs/ui-data-layer.md` budgets zero page-level client JS for article and
 * index pages and allows it for a handful of interactive surfaces; a sign-in
 * form is squarely one of them — it needs to POST, hold a pending state, and
 * show an error without a full round trip.
 *
 * It posts to `/api/staff-login`, never to Payload's `/api/users/login`,
 * which is disabled (see the page beside this one).
 */
export function StaffLoginForm() {
  const router = useRouter()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setPending(true)

    const data = new FormData(event.currentTarget)
    try {
      const response = await fetch('/api/staff-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: String(data.get('email') ?? ''),
          password: String(data.get('password') ?? ''),
        }),
        // The session cookie is the entire point of this request.
        credentials: 'same-origin',
      })

      if (response.ok) {
        // `refresh()` before `push()` so the server components on the next
        // page re-run with the cookie now set, rather than rendering from a
        // cache that still believes nobody is signed in.
        router.refresh()
        router.push('/team-editor')
        return
      }

      const body = await response.json().catch(() => ({}))
      // The server decides what is safe to say — an unknown address and a
      // wrong password deliberately produce the same message, so the form
      // must not try to be more helpful than that.
      setError(body?.message ?? 'Sign-in failed. Please try again.')
    } catch {
      setError('Sign-in is temporarily unavailable. Please try again shortly.')
    } finally {
      setPending(false)
    }
  }

  return (
    <form onSubmit={onSubmit} style={{ marginTop: 'var(--space-l)', display: 'grid', gap: 'var(--space-m)' }}>
      <label style={{ display: 'grid', gap: 'var(--space-2xs)' }}>
        <span className="kicker">Email</span>
        <input
          name="email"
          type="email"
          required
          autoComplete="username"
          autoFocus
          style={{ padding: 'var(--space-s)', font: 'inherit', border: '1px solid currentColor' }}
        />
      </label>

      <label style={{ display: 'grid', gap: 'var(--space-2xs)' }}>
        <span className="kicker">Password</span>
        <input
          name="password"
          type="password"
          required
          autoComplete="current-password"
          style={{ padding: 'var(--space-s)', font: 'inherit', border: '1px solid currentColor' }}
        />
      </label>

      {error ? (
        <p role="alert" className="dek" style={{ color: 'var(--c-red, #b00)', margin: 0 }}>
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={pending}
        className="kicker kicker--red"
        style={{
          padding: 'var(--space-s)',
          border: '1px solid currentColor',
          background: 'transparent',
          cursor: pending ? 'progress' : 'pointer',
        }}
      >
        {pending ? 'Signing in…' : 'Sign in →'}
      </button>
    </form>
  )
}
