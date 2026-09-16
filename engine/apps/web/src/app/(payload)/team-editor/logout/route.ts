/**
 * Sign-out for the merged admin.
 *
 * **Why this route has to exist.** Payload's nav renders "Log out" as a plain
 * link to `<admin>/logout`, and its own view for that path ends up calling
 * `POST /api/users/logout`, which expires the cookie named
 * `<cookiePrefix>-token` — `payload-token`. This deployment's session is not
 * that cookie. It is `__Host-now-staff`, issued by `/api/staff-login` against
 * the *platform* identity store, because the collection sets
 * `disableLocalStrategy` and Payload's own login cannot reach it
 * (docs/ADMIN-CONSOLIDATION.md Phase 1).
 *
 * So the sign-out that shipped cleared a cookie that does not exist here. It
 * looked right from the outside — the click landed on `/team-editor/login`,
 * which is exactly what a successful sign-out looks like — while the session
 * cookie survived untouched and `/team-editor` still rendered the dashboard
 * to the next person at the keyboard. On a shared machine that is not a
 * cosmetic bug.
 *
 * A route handler rather than a page: clearing a cookie is a mutation, and
 * Next only permits `cookies().set()` from a route handler or a server
 * action, never from a component's render. It wins over Payload's
 * `[[...segments]]` catch-all the same way `/team-editor/login` does — Next
 * gives a static segment precedence over a dynamic one.
 *
 * GET as well as POST, because the thing that links here is an anchor and we
 * do not control that markup. A forged GET can sign a user out and nothing
 * else; that is an annoyance, not an escalation, and the alternative is a
 * sign-out button that does not work.
 *
 * **This is a client-side logout only.** The token stays valid until it
 * expires; nothing server-side revokes it, so a copy captured beforehand
 * still works. Closing that needs a revocation list or per-session rows,
 * which is deliberately not built yet — the 8h TTL is the bound. Worth
 * revisiting if staff ever sign in from machines they do not control.
 */

import { SESSION_COOKIE, sessionCookieOptions } from '@now/auth'
import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

async function signOut(request: Request): Promise<Response> {
  // Same origin as the request, so this works on either city's hostname
  // without either being named here (ARCHITECTURE.md §3.5).
  const response = NextResponse.redirect(new URL('/team-editor/login', request.url), 303)

  // Every attribute the cookie was set with, or the browser keeps the
  // original: a `__Host-` cookie can only be cleared by a `__Host-` write,
  // and only one that matches on path and the Secure flag.
  response.cookies.set(SESSION_COOKIE, '', { ...sessionCookieOptions(), maxAge: 0 })

  return response
}

export const GET = signOut
export const POST = signOut
