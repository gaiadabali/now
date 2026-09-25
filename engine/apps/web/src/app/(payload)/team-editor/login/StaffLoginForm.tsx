'use client'

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
 *
 * Presentation is entirely in `styles/admin.css` under `.staff-login__*`.
 * It used to be inline styles referencing `--space-*` and `.kicker` from the
 * reader site's stylesheets — none of which are loaded under Payload's root
 * layout, so every one of them resolved to nothing and the form rendered as
 * raw browser defaults.
 *
 * `destination` is resolved on the server (see the page beside this one) so
 * that the untrusted `?redirect=` value is validated once, somewhere it
 * cannot be skipped, rather than by this component reading the query string
 * for itself.
 */
export function StaffLoginForm({ destination }: { destination: string }) {
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
        // A HARD navigation, not `router.refresh(); router.push(destination)`.
        // That was the original approach and it does not do what its own
        // comment says: `@payloadcms/ui`'s `AuthProvider` seeds its `user`
        // state from an `initialUser` PROP with a bare `useState(initialUser)`
        // — which only ever reads that argument on the component's first
        // mount. `router.refresh()` re-runs the server components and would
        // hand the ROOT LAYOUT a fresh `initialUser`, but `AuthProvider`
        // itself is not remounted by a refresh, so the new prop value never
        // reaches its state. Every nav item gated on `useAuth()` — nav/
        // StaffLink.tsx, nav/NavPlatform.tsx, both plain `'use client'`
        // components with no server prop of their own — kept reading the
        // signed-OUT snapshot from the moment the login PAGE first mounted,
        // until the next full page load. (`NavConsole`'s Commerce group is
        // NOT one of these: it takes `user` as an ordinary server prop
        // rather than through this context, which is exactly why it kept
        // working — the bug is specific to the client auth context, not to
        // "the sidebar" in general.)
        //
        // Found by comparing two ways of reaching an authenticated page in
        // the same tour: a hard `page.goto()` with an already-valid cookie
        // rendered the full sidebar every time; a scripted sign-in through
        // this form, followed by the soft navigation this replaces, rendered
        // a signed-in dashboard with an admin-only sidebar missing its
        // admin-only links — same account, same role, same request's `/api/
        // users/me` answering "admin" correctly the whole time. The bug was
        // never about which city; it was about which navigation this form
        // performed after a correct sign-in.
        window.location.assign(destination)
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
    <form className="staff-login__form" onSubmit={onSubmit}>
      <label className="staff-login__label">
        <span>Email</span>
        <input
          className="staff-login__input"
          name="email"
          type="email"
          required
          autoComplete="username"
          autoFocus
        />
      </label>

      <label className="staff-login__label">
        <span>Password</span>
        <input
          className="staff-login__input"
          name="password"
          type="password"
          required
          autoComplete="current-password"
        />
      </label>

      {error ? (
        <p role="alert" className="staff-login__error">
          {error}
        </p>
      ) : null}

      <button className="staff-login__submit" type="submit" disabled={pending}>
        {pending ? 'Signing in…' : 'Sign in'}
      </button>

      {/* One account opens both cities (docs/ADMIN-CONSOLIDATION.md): worth
          saying here, because the mark above the form implies the opposite. */}
      <p className="staff-login__note">One staff account works across every NOW! city.</p>
    </form>
  )
}
