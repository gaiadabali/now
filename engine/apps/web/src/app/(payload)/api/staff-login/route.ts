/**
 * `POST /api/staff-login` — the city CMS's sign-in.
 *
 * Replaces Payload's own `/api/users/login`, which is gone because the
 * collection sets `disableLocalStrategy: true` (see
 * `src/auth/platformStrategy.ts` for why). The credential lives in
 * `now_platform.public.users`; this route is the only place a city app checks
 * one.
 *
 *   1. verify against the platform          @now/auth `authenticate`
 *   2. project the user into this city      @now/auth `upsertShadowUser`
 *   3. issue a signed token in a cookie     @now/auth `issueSessionToken`
 *
 * Step 2 matters: Payload issues its session against a row in *its own*
 * database, so a first-time signer-in needs one created before the strategy
 * can find them.
 */

import {
  SESSION_COOKIE,
  PostgresIdentityStore,
  authenticate,
  createPool,
  issueSessionToken,
  sessionCookieOptions,
  upsertShadowUser,
} from '@now/auth'
import { NextResponse } from 'next/server'

// Module-scope pools: a route handler runs per request, and building a pool
// per sign-in would leak connections under any real load.
let platformPool: ReturnType<typeof createPool> | null = null
let cityPool: ReturnType<typeof createPool> | null = null

function pools() {
  const platformUri = process.env.PLATFORM_DATABASE_URI
  const cityUri = process.env.DATABASE_URI
  if (!platformUri || !cityUri) {
    throw new Error('PLATFORM_DATABASE_URI and DATABASE_URI must both be set')
  }
  platformPool ??= createPool(platformUri)
  cityPool ??= createPool(cityUri)
  return { platformPool, cityPool }
}

/**
 * One message for every failure a caller could use to enumerate accounts.
 * `locked` and `unavailable` are distinguishable on purpose: both are
 * actionable by a legitimate user and neither reveals whether an address
 * exists — `locked` is only ever reached after a correct identification.
 */
const MESSAGES = {
  invalid_credentials: 'Incorrect email or password.',
  no_access: 'This account has no access. Ask an administrator to grant a role.',
  locked: 'Too many attempts. Try again in a few minutes.',
  unavailable: 'Sign-in is temporarily unavailable. Please try again shortly.',
} as const

export async function POST(request: Request): Promise<Response> {
  const secret = process.env.PAYLOAD_SECRET
  if (!secret) {
    return NextResponse.json({ message: MESSAGES.unavailable }, { status: 503 })
  }

  let email: unknown
  let password: unknown
  try {
    const body = await request.json()
    email = body?.email
    password = body?.password
  } catch {
    return NextResponse.json({ message: MESSAGES.invalid_credentials }, { status: 400 })
  }

  if (typeof email !== 'string' || typeof password !== 'string' || !email || !password) {
    return NextResponse.json({ message: MESSAGES.invalid_credentials }, { status: 400 })
  }

  let result
  try {
    const { platformPool, cityPool } = pools()
    result = await authenticate(email, password, {
      store: new PostgresIdentityStore(platformPool),
    })

    if (!result.ok) {
      // 401 for a bad credential, 423 for a lock, 503 for an outage — so a
      // client can tell "try again later" from "you typed it wrong", without
      // the body ever saying which account exists.
      const status =
        result.reason === 'locked' ? 423 : result.reason === 'unavailable' ? 503 : 401
      return NextResponse.json({ message: MESSAGES[result.reason] }, { status })
    }

    const shadowId = await upsertShadowUser(cityPool, result.user)
    const token = issueSessionToken(
      {
        shadowId,
        email: result.user.email,
        editorialRole: result.user.editorialRole,
        commerceRole: result.user.commerceRole,
      },
      secret,
    )

    const response = NextResponse.json({
      user: {
        email: result.user.email,
        name: result.user.name,
        editorialRole: result.user.editorialRole,
        commerceRole: result.user.commerceRole,
      },
    })
    response.cookies.set(SESSION_COOKIE, token, sessionCookieOptions())
    return response
  } catch (error) {
    // Never let a database error reach the client verbatim: connection
    // strings and hostnames end up in messages.
    console.error('[staff-login] unexpected failure', error)
    return NextResponse.json({ message: MESSAGES.unavailable }, { status: 503 })
  }
}
