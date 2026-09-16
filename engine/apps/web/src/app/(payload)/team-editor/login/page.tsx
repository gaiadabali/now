import type { Metadata } from 'next'
import { redirect } from 'next/navigation'
import { getSafeRedirect } from 'payload/shared'

import { currentUser } from '@/lib/auth'
import { getSiteConfig } from '@/lib/site'

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
 *
 * It also carries the city's logo, which is more than decoration on a shared
 * sign-in: one account now opens both cities, so the mark above the form is
 * the only thing on screen that says which one this is.
 */

export const metadata: Metadata = {
  title: 'Sign in',
  // An admin login has no business in an index, and this one now sits on a
  // public hostname rather than behind its own.
  robots: { index: false, follow: false },
}

export default async function StaffLoginPage({
  searchParams,
}: {
  searchParams: Promise<{ redirect?: string }>
}) {
  const [site, params] = await Promise.all([getSiteConfig(), searchParams])

  /**
   * Where to go once signed in.
   *
   * Payload sends anyone who hits a protected screen while signed out to
   * `…/login?redirect=<where they were going>`. This page ignored that and
   * always landed on the dashboard, so an editor following a link to a
   * document — from a colleague, from an email — signed in and then had to
   * find it again by hand.
   *
   * `getSafeRedirect` is Payload's own, not a hand-rolled check: `redirect`
   * is attacker-controllable, and the list of things that have to be
   * rejected (protocol-relative `//host`, `/\host`, `/%2F`, encoded control
   * characters, `/javascript:`) is longer than it first looks. Anything that
   * fails falls back to the dashboard.
   */
  const destination = getSafeRedirect({
    fallbackTo: '/team-editor',
    // `?? ''` because the parameter is not optional in Payload's signature;
    // an empty string fails its checks and lands on the fallback, which is
    // exactly what a missing `redirect` should do.
    redirectTo: params.redirect ?? '',
  })

  // Already signed in: send them on rather than presenting a form that would
  // re-authenticate the session they already hold. Payload's own login view
  // does exactly this, and skipping it here meant a stale bookmark to /login
  // looked like a signed-out state.
  if (await currentUser()) redirect(destination)

  return (
    // Payload's own centring shell, by name. This page sits inside Payload's
    // root layout and its stylesheet is already loaded, so borrowing the
    // template it uses for login and verify costs nothing and keeps the two
    // screens from drifting apart the next time Payload changes it.
    <section className="template-minimal template-minimal--width-normal">
      <div className="template-minimal__wrap staff-login">
        <div className="staff-login__brand">
          {/* eslint-disable-next-line @next/next/no-img-element -- a local
              SVG wordmark; there is nothing for next/image to optimise. */}
          <img className="staff-login__logo" src={site.brand.logo} alt={site.brand.logoAlt} />
        </div>

        <p className="staff-login__kicker">Team editor</p>
        <h1 className="staff-login__title">Sign in</h1>

        <StaffLoginForm destination={destination} />
      </div>
    </section>
  )
}
