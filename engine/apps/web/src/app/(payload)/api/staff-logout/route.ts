/**
 * `POST /api/staff-logout` — clears the staff session cookie.
 *
 * Payload's own logout endpoint is gone with the local strategy, and a user
 * who cannot sign out on a shared machine is a real problem, not a missing
 * nicety.
 *
 * **This is a client-side logout only.** The token stays valid until it
 * expires; nothing server-side revokes it, so a copy captured beforehand
 * still works. Closing that needs a revocation list or per-session rows,
 * which is deliberately not built yet — the 8h TTL is the bound. Worth
 * revisiting if staff ever sign in from machines they do not control.
 */

import { SESSION_COOKIE } from '@now/auth'
import { NextResponse } from 'next/server'

export async function POST(): Promise<Response> {
  const response = NextResponse.json({ ok: true })
  // Same attributes the cookie was set with, or the browser keeps the
  // original: a __Host- cookie can only be cleared by a __Host- write.
  response.cookies.set(SESSION_COOKIE, '', {
    httpOnly: true,
    secure: true,
    sameSite: 'lax',
    path: '/',
    maxAge: 0,
  })
  return response
}
