/**
 * The custom Payload auth strategy for a city CMS.
 *
 * Phase 1 of docs/ADMIN-CONSOLIDATION.md. Staff identity lives in
 * `now_platform.public.users`; this Payload instance is bound to a **city**
 * database and so cannot check a password itself. The split is:
 *
 *   src/app/(payload)/api/staff-login  verifies against the platform,
 *                                      upserts the shadow row, issues a token
 *   this file                          trades that token back for the shadow
 *                                      user on every request
 *
 * `disableLocalStrategy: true` on the collection is what makes this safe.
 * Without it Payload would still accept a password against the city `users`
 * table — and while the shadow rows carry NULL hash/salt (so none of them
 * could authenticate), any row an admin created by hand *would*, quietly
 * reintroducing a second, unmanaged way in.
 *
 * **What this strategy does not do.** It does not re-check the platform on
 * every request. The token carries a copy of the roles, so a revocation takes
 * effect when the token expires (8h) and the user signs in again — the
 * trade-off named in session.ts. Re-reading the platform per request would
 * close that window at the cost of a cross-database query on every admin
 * page load; if that becomes the right trade, this is the one function to
 * change.
 */

import type { AuthStrategyFunction, AuthStrategyResult } from 'payload'

import { SESSION_COOKIE, type VerifyResult, verifySessionToken } from '@now/auth'

const UNAUTHENTICATED: AuthStrategyResult = { user: null }

/**
 * An explicit guard rather than relying on `if (!result.ok)` to narrow.
 *
 * This package compiles with `strict: false`, and without `strictNullChecks`
 * TypeScript does not narrow a discriminated union on a literal boolean — so
 * the `reason` branch below fails to typecheck even though the logic is
 * sound. A user-defined type predicate works either way, and is clearer about
 * the intent than a cast would be.
 */
function isFailure(result: VerifyResult): result is Extract<VerifyResult, { ok: false }> {
  return result.ok === false
}

/**
 * Reads a cookie out of a `Headers` object.
 *
 * Deliberately not a regex over the whole header: cookie values are opaque
 * and may contain anything, and a greedy pattern can match a *different*
 * cookie whose name merely ends with ours (`evil-__Host-now-staff=…`).
 * Splitting on `;` and comparing the name exactly avoids that.
 */
function readCookie(headers: Headers, name: string): string | null {
  const header = headers.get('cookie')
  if (!header) return null

  for (const part of header.split(';')) {
    const eq = part.indexOf('=')
    if (eq === -1) continue
    if (part.slice(0, eq).trim() !== name) continue
    return decodeURIComponent(part.slice(eq + 1).trim())
  }
  return null
}

export const platformStrategy: AuthStrategyFunction = async ({ headers, payload }) => {
  const secret = process.env.PAYLOAD_SECRET
  if (!secret) {
    // Refusing beats guessing. A missing secret must not degrade to "let
    // everyone in"; it is a deployment fault and every request fails closed.
    payload.logger.error('PAYLOAD_SECRET is unset — refusing every staff session')
    return UNAUTHENTICATED
  }

  const token = readCookie(headers, SESSION_COOKIE)
  if (!token) return UNAUTHENTICATED

  const verified = verifySessionToken(token, secret)
  if (isFailure(verified)) {
    // `expired` is the ordinary end of a session and is not worth a log line
    // per request; a bad signature is someone trying something.
    if (verified.reason === 'bad_signature') {
      payload.logger.warn('staff session token failed signature verification')
    }
    return UNAUTHENTICATED
  }

  // The shadow row is looked up by id every request rather than trusted from
  // the token, so a user deleted from this city stops being able to act here
  // immediately, without waiting for their token to expire.
  const user = await payload.findByID({
    collection: 'users',
    id: verified.claims.shadowId,
    depth: 0,
    overrideAccess: true,
    disableErrors: true,
  })

  if (!user) return UNAUTHENTICATED

  // The token's email must still match the row it names. Ids are sequential,
  // so a token for a deleted user could otherwise land on whoever later
  // inherited that id.
  //
  // This depends on `email` being declared explicitly on the collection:
  // `disableLocalStrategy` removes the auth fields Payload would otherwise
  // synthesise, so without that declaration `user.email` is `undefined` here
  // and this guard refuses every valid session. It fails closed, which is the
  // right direction -- but it does fail.
  if (String(user.email).toLowerCase() !== verified.claims.email.toLowerCase()) {
    payload.logger.warn(
      { shadowId: verified.claims.shadowId },
      'staff session token id/email mismatch — refusing',
    )
    return UNAUTHENTICATED
  }

  return {
    user: {
      ...user,
      collection: 'users',
      // Roles come from the TOKEN, not the shadow row: the token is what the
      // platform signed. The shadow's own `role` column is a projection
      // refreshed at sign-in and is not authoritative.
      role: verified.claims.editorialRole,
      commerceRole: verified.claims.commerceRole,
      _strategy: 'platform-identity',
    },
  } as AuthStrategyResult
}
