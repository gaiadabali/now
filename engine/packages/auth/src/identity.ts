/**
 * Authenticating a staff member against the platform identity store.
 *
 * `now_platform.public.users` is the single source of truth (see
 * docs/ADMIN-CONSOLIDATION.md). This module owns the *decision* — valid or
 * not, locked or not — and knows nothing about Postgres; `store.ts` is the
 * only file that does. That split is why the whole lockout and
 * role-refresh policy can be tested exhaustively with an in-memory fake,
 * which matters more here than anywhere else in the repo.
 */

import { verifyPassword } from './password.ts'

export const STAFF_ROLES = ['admin', 'partner_manager', 'viewer'] as const
export type StaffRole = (typeof STAFF_ROLES)[number]

export function isStaffRole(value: unknown): value is StaffRole {
  return typeof value === 'string' && (STAFF_ROLES as readonly string[]).includes(value)
}

export type PlatformUser = {
  id: number
  email: string
  name: string | null
  role: StaffRole
  hash: string | null
  salt: string | null
  loginAttempts: number
  lockUntil: Date | null
}

/** What a successful sign-in hands back. Deliberately carries no secret. */
export type AuthenticatedUser = {
  platformId: number
  email: string
  name: string | null
  role: StaffRole
}

export type AuthFailure =
  | 'invalid_credentials'
  | 'locked'
  | 'unavailable'

export type AuthResult =
  | { ok: true; user: AuthenticatedUser }
  | { ok: false; reason: AuthFailure }

export interface IdentityStore {
  findByEmail(email: string): Promise<PlatformUser | null>
  recordFailedAttempt(userId: number, lockUntil: Date | null): Promise<void>
  clearFailedAttempts(userId: number): Promise<void>
}

export type LockoutPolicy = {
  maxAttempts: number
  lockMs: number
}

/**
 * Mirrors the console's existing Users collection so behaviour does not
 * change as sign-in moves: `maxLoginAttempts: 8`, `lockTime: 10 * 60 * 1000`.
 * Commercial data behind a login that allows unlimited guesses is a login in
 * name only.
 */
export const DEFAULT_LOCKOUT: LockoutPolicy = {
  maxAttempts: 8,
  lockMs: 10 * 60 * 1000,
}

export type AuthenticateOptions = {
  store: IdentityStore
  lockout?: LockoutPolicy
  /** Injectable for tests; never pass in production. */
  now?: () => Date
}

/**
 * Verifies an email/password pair.
 *
 * **Every failure returns `invalid_credentials`, whatever actually went
 * wrong.** An unknown address and a wrong password must be indistinguishable
 * to the caller, or the sign-in form becomes an oracle for which staff
 * addresses exist. `locked` is the one exception and is deliberate: telling a
 * locked-out user to wait is worth more than the small amount it reveals, and
 * it only ever appears *after* correct identification of an existing account.
 *
 * A store that throws yields `unavailable`, never `invalid_credentials` — a
 * database outage must not look to the user like a mistyped password, and
 * must not be counted as a failed attempt against them.
 */
export async function authenticate(
  email: string,
  password: string,
  options: AuthenticateOptions,
): Promise<AuthResult> {
  const { store } = options
  const lockout = options.lockout ?? DEFAULT_LOCKOUT
  const now = options.now ?? (() => new Date())

  let user: PlatformUser | null
  try {
    user = await store.findByEmail(normaliseEmail(email))
  } catch {
    return { ok: false, reason: 'unavailable' }
  }

  if (!user) {
    // No row to count an attempt against. The timing difference between this
    // path and a real pbkdf2 is a known, accepted leak: closing it means
    // hashing against a dummy credential on every unknown address, which
    // costs 25k iterations per unauthenticated request and turns the sign-in
    // form into an amplification vector. Rate limiting is the right control
    // for enumeration, and it belongs in front of this function.
    return { ok: false, reason: 'invalid_credentials' }
  }

  if (user.lockUntil && user.lockUntil.getTime() > now().getTime()) {
    return { ok: false, reason: 'locked' }
  }

  const valid = await verifyPassword(password, { hash: user.hash, salt: user.salt })

  if (!valid) {
    const attempts = user.loginAttempts + 1
    const lockUntil =
      attempts >= lockout.maxAttempts ? new Date(now().getTime() + lockout.lockMs) : null
    try {
      await store.recordFailedAttempt(user.id, lockUntil)
    } catch {
      // The credential was still wrong. Failing to record the attempt is a
      // problem for lockout, not a reason to admit the user.
    }
    return { ok: false, reason: 'invalid_credentials' }
  }

  if (!isStaffRole(user.role)) {
    // A role this build does not recognise is not a licence to fall back to
    // something permissive. Refuse, and let a human fix the row.
    return { ok: false, reason: 'invalid_credentials' }
  }

  try {
    await store.clearFailedAttempts(user.id)
  } catch {
    // Non-fatal: the password was correct. A stale attempt counter costs the
    // user a few guesses next time, which is the safe direction to fail.
  }

  return {
    ok: true,
    user: {
      platformId: user.id,
      email: user.email,
      name: user.name,
      role: user.role,
    },
  }
}

/**
 * Payload lowercases and trims email on save, so a lookup that does not match
 * that would let `Hansel@…` fail while `hansel@…` succeeds.
 */
export function normaliseEmail(email: string): string {
  return email.trim().toLowerCase()
}
