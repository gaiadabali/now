import type { Metadata } from 'next'

import { StaffLoginForm } from './StaffLoginForm'

/**
 * Sign-in for the merged admin.
 *
 * **Why this page has to exist.** Payload's own login form posts to
 * `/api/users/login`, and the city `users` collection sets
 * `disableLocalStrategy: true` — so that endpoint returns 403 and Payload's
 * built-in form can never succeed. Without this page the admin is reachable,
 * renders, redirects you to `/team-editor/login`… and there is no way in.
 * A complete lockout, produced by a setting that is otherwise correct.
 *
 * The credential lives in `now_platform.public.users`, which this app's
 * Payload instance cannot reach (it binds the city database), so sign-in goes
 * through `/api/staff-login` — verify against the platform, project a shadow
 * row, issue the session cookie (docs/ADMIN-CONSOLIDATION.md Phase 1).
 *
 * This route wins over Payload's `[[...segments]]` catch-all because Next
 * gives a static segment precedence over a dynamic one.
 */

export const metadata: Metadata = {
  title: 'Sign in',
  // An admin login has no business in an index, and this one now sits on a
  // public hostname rather than behind its own.
  robots: { index: false, follow: false },
}

export default function StaffLoginPage() {
  return (
    <div className="shell band" style={{ maxWidth: '26rem', paddingBlock: 'var(--space-3xl)' }}>
      <p className="kicker kicker--red">Staff</p>
      <h1
        className="display display--light"
        style={{ fontSize: 'var(--t-h1)', marginTop: 'var(--space-2xs)' }}
      >
        Sign in
      </h1>
      <StaffLoginForm />
    </div>
  )
}
