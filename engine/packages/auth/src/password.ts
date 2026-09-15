/**
 * Password verification, byte-compatible with Payload's local strategy.
 *
 * This file reimplements one function from `payload/dist/auth/strategies/
 * local/authenticate.js`, and it is the single most security-critical thing
 * in this package. It exists because the city applications must verify a
 * credential stored in `now_platform.public.users` while their own Payload
 * instance is bound to a *city* database — Payload binds exactly one database
 * per instance, so its own login operation cannot reach the platform table.
 *
 * The parameters below are not chosen, they are *matched*. Payload 3.88.0
 * generates and checks with:
 *
 *     crypto.pbkdf2(password, salt, 25000, 512, 'sha256')   // hash stored hex
 *
 * Any drift here silently rejects every valid password, or — far worse —
 * accepts an invalid one. Two defences:
 *
 *   1. `test/password.test.ts` verifies against hash/salt pairs **Payload
 *      itself produced**, not against our own output. A test that hashes with
 *      the same code it is testing proves nothing.
 *   2. `PBKDF2` below is exported so the constants are greppable from one
 *      place if Payload ever changes them.
 *
 * Comparison uses `timingSafeEqual`, as Payload's does. A `===` on hex
 * strings leaks the length of the matching prefix through timing, which over
 * enough attempts is a practical attack, not a theoretical one.
 */

import crypto from 'node:crypto'

/** Matched to Payload 3.88.0. See module docstring before touching. */
export const PBKDF2 = {
  iterations: 25_000,
  keylen: 512,
  digest: 'sha256',
} as const

export type StoredCredential = {
  /** hex-encoded pbkdf2 output */
  hash: string | null
  /** hex-encoded random salt */
  salt: string | null
}

/**
 * True when `password` matches the stored credential.
 *
 * Returns false rather than throwing for a missing hash or salt: a user row
 * with no credential (created by an admin who never set a password, or a
 * shadow row that deliberately carries none) must be unauthenticatable, not
 * an error that a caller might mistake for a transport failure and retry.
 */
export async function verifyPassword(
  password: string,
  credential: StoredCredential,
): Promise<boolean> {
  const { hash, salt } = credential
  if (typeof hash !== 'string' || typeof salt !== 'string') return false
  if (hash.length === 0 || salt.length === 0) return false

  let storedHash: Buffer
  try {
    storedHash = Buffer.from(hash, 'hex')
  } catch {
    return false
  }
  // `Buffer.from(<non-hex>, 'hex')` truncates rather than throwing, so a
  // malformed hash becomes a short buffer instead of an error. Length is
  // checked before the comparison below, which catches that.
  if (storedHash.length !== PBKDF2.keylen) return false

  const computed = await pbkdf2(password, salt)
  return crypto.timingSafeEqual(computed, storedHash)
}

function pbkdf2(password: string, salt: string): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    crypto.pbkdf2(
      password,
      salt,
      PBKDF2.iterations,
      PBKDF2.keylen,
      PBKDF2.digest,
      (err, derived) => (err ? reject(err) : resolve(derived)),
    )
  })
}

/**
 * Produces a Payload-compatible credential. Used by the migration that moves
 * existing city users into the platform table, and by tests.
 *
 * Deliberately NOT used to set passwords at runtime: the platform Payload
 * instance owns password changes, so there is exactly one code path that
 * writes a credential. This one exists for migration, where there is no
 * Payload instance to ask.
 */
export async function hashPassword(password: string): Promise<{ hash: string; salt: string }> {
  const salt = crypto.randomBytes(32).toString('hex')
  const derived = await pbkdf2(password, salt)
  return { hash: derived.toString('hex'), salt }
}
