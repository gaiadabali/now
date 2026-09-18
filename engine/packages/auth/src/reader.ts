/**
 * Reader accounts: registration, sign-in, and the single-use email tokens
 * behind verification and password reset (E8.2).
 *
 * Structured exactly like `identity.ts` — policy here, storage behind a
 * `ReaderStore` interface — so lockout, enumeration behaviour and token expiry
 * are testable without a database. That seam is why staff lockout has real
 * tests, and readers get the same.
 *
 * Readers are **not** staff and this does not touch `public.users`. See
 * docs/READER-IDENTITY.md for why the stores are separate; the short version
 * is that the staff table is shadow-projected into every city database, and a
 * reader must never be one wrong `role` value away from a CMS session.
 */

import crypto from 'node:crypto'

import { PBKDF2, hashPassword, verifyPassword } from './password.ts'
import type { StoredCredential } from './password.ts'

export type ReaderStatus = 'active' | 'suspended' | 'deleted'

export type ReaderRecord = {
  id: string
  email: string
  emailNorm: string
  name: string | null
  hash: string | null
  salt: string | null
  emailVerifiedAt: Date | null
  loginAttempts: number
  lockUntil: Date | null
  status: ReaderStatus
  /**
   * When they joined. Nullable because a store is not obliged to supply it —
   * the in-memory test store does not — and because nothing here should fail
   * for want of a date that is only ever used to greet someone.
   */
  createdAt: Date | null
}

export type EmailTokenKind = 'verify_email' | 'reset_password'

export type EmailTokenRecord = {
  id: string
  identityId: string
  kind: EmailTokenKind
  expiresAt: Date
  consumedAt: Date | null
}

export interface ReaderStore {
  findByEmail(emailNorm: string): Promise<ReaderRecord | null>
  findById(id: string): Promise<ReaderRecord | null>
  create(input: {
    email: string
    emailNorm: string
    name: string | null
    credential: StoredCredential
  }): Promise<ReaderRecord>
  recordFailedAttempt(id: string, lockUntil: Date | null): Promise<void>
  clearFailedAttempts(id: string, lastLoginAt: Date): Promise<void>
  setPassword(id: string, credential: StoredCredential): Promise<void>
  markEmailVerified(id: string, at: Date): Promise<void>

  createToken(input: {
    identityId: string
    kind: EmailTokenKind
    tokenHash: string
    expiresAt: Date
  }): Promise<void>
  findTokenByHash(tokenHash: string): Promise<EmailTokenRecord | null>
  consumeToken(id: string, at: Date): Promise<void>
  /** Invalidate a person's outstanding tokens of one kind. */
  deleteTokens(identityId: string, kind: EmailTokenKind): Promise<void>
}

/** Same shape and defaults as the staff policy in `identity.ts`. */
export type ReaderLockoutPolicy = {
  maxAttempts: number
  lockMinutes: number
}

export const DEFAULT_READER_LOCKOUT: ReaderLockoutPolicy = { maxAttempts: 10, lockMinutes: 15 }

/** `lower(btrim(x))` — exactly what migration 0007 stores in `email_norm`. */
export function normaliseReaderEmail(raw: string): string {
  return raw.trim().toLowerCase()
}

// --- password policy -------------------------------------------------------

export type PasswordProblem = 'too_short' | 'too_long' | 'too_common'

export type PasswordCheck = { ok: true } | { ok: false; reason: PasswordProblem }

/**
 * Length, and a short list of the passwords people actually pick.
 *
 * Deliberately not a composition rule ("one uppercase, one symbol"). Those
 * measurably push people toward `Password1!` — they add a predictable suffix
 * to the same weak root — and NIST dropped the recommendation for that reason.
 * Length plus a blocklist is what remains.
 *
 * 12 rather than 8. A reader account holds a reading history and a saved-place
 * list, which is not nothing, and the cost of two extra characters at
 * registration is lower than the cost of an account takeover nobody notices.
 */
export const MIN_PASSWORD_LENGTH = 12
/** bcrypt-era truncation does not apply to PBKDF2, but an unbounded input is a DoS. */
export const MAX_PASSWORD_LENGTH = 256

const COMMON = new Set([
  'password', 'password1', 'password123', 'passw0rd', '123456', '1234567',
  '12345678', '123456789', '1234567890', 'qwerty', 'qwertyuiop', 'letmein',
  'welcome', 'admin', 'iloveyou', 'monkey', 'dragon', 'football', 'baseball',
  'abc123', 'trustno1', 'sunshine', 'princess', 'starwars', 'whatever',
  'jakarta', 'indonesia', 'nowjakarta', 'nowbali', 'bali',
])

export function checkPassword(password: string): PasswordCheck {
  if (password.length < MIN_PASSWORD_LENGTH) return { ok: false, reason: 'too_short' }
  if (password.length > MAX_PASSWORD_LENGTH) return { ok: false, reason: 'too_long' }
  // Case- and digit-suffix-insensitive: `Password123` is `password`.
  const root = password.toLowerCase().replace(/[0-9!@#$%^&*._-]+$/, '')
  if (COMMON.has(password.toLowerCase()) || COMMON.has(root)) {
    return { ok: false, reason: 'too_common' }
  }
  return { ok: true }
}

// --- registration ----------------------------------------------------------

export type RegisterFailure = 'invalid_email' | 'weak_password' | 'already_registered'

export type RegisterResult =
  | { ok: true; reader: ReaderRecord }
  | { ok: false; reason: RegisterFailure; detail?: PasswordProblem }

export type RegisterInput = {
  email: string
  password: string
  name?: string | null
}

/**
 * Creates a reader.
 *
 * **`already_registered` is returned to the caller, not shown to the visitor.**
 * A registration form that says "this address is taken" is an account
 * enumeration oracle — anyone can test an address list against it. The route
 * above this should respond identically whether or not the address existed,
 * and send a "someone tried to register with your address; you already have an
 * account" mail to the real owner instead. That decision belongs at the route
 * because only the route can send the mail; this function's job is to report
 * honestly.
 */
export async function registerReader(
  store: ReaderStore,
  input: RegisterInput,
  options: { now?: () => Date } = {},
): Promise<RegisterResult> {
  const email = input.email.trim()
  const emailNorm = normaliseReaderEmail(email)
  if (emailNorm.length < 5 || !emailNorm.includes('@')) {
    return { ok: false, reason: 'invalid_email' }
  }

  const password = checkPassword(input.password)
  if (!password.ok) return { ok: false, reason: 'weak_password', detail: password.reason }

  const existing = await store.findByEmail(emailNorm)
  if (existing) return { ok: false, reason: 'already_registered' }

  const credential = await hashPassword(input.password)
  const reader = await store.create({
    email,
    emailNorm,
    name: input.name?.trim() || null,
    credential,
  })
  void options
  return { ok: true, reader }
}

// --- sign-in ---------------------------------------------------------------

export type ReaderAuthFailure =
  | 'invalid_credentials'
  | 'locked'
  | 'unverified'
  | 'suspended'
  | 'unavailable'

export type ReaderAuthResult =
  | { ok: true; reader: ReaderRecord }
  | { ok: false; reason: ReaderAuthFailure }

export type ReaderAuthOptions = {
  lockout?: ReaderLockoutPolicy
  now?: () => Date
  /**
   * Whether an unverified address may sign in.
   *
   * Default `true`, and that is a product call rather than a lax one. Blocking
   * sign-in until verification means anyone whose confirmation mail bounces,
   * is filtered, or simply never arrives has an account they cannot reach and
   * no way to ask for another. Signing them in and gating the parts that
   * genuinely need a proven address is recoverable; locking them out is not.
   */
  allowUnverified?: boolean
}

export async function authenticateReader(
  store: ReaderStore,
  email: string,
  password: string,
  options: ReaderAuthOptions = {},
): Promise<ReaderAuthResult> {
  const lockout = options.lockout ?? DEFAULT_READER_LOCKOUT
  const now = options.now ?? (() => new Date())
  const allowUnverified = options.allowUnverified ?? true

  const reader = await store.findByEmail(normaliseReaderEmail(email))

  // Same response for "no such address" and "wrong password", and the same
  // work done either way — see the dummy verify below.
  if (!reader) {
    await burnTime(password)
    return { ok: false, reason: 'invalid_credentials' }
  }

  if (reader.status === 'deleted') {
    // A deleted account is indistinguishable from one that never existed.
    await burnTime(password)
    return { ok: false, reason: 'invalid_credentials' }
  }
  if (reader.status === 'suspended') return { ok: false, reason: 'suspended' }

  if (reader.lockUntil && reader.lockUntil.getTime() > now().getTime()) {
    return { ok: false, reason: 'locked' }
  }

  // An identity with no credential — created by an import, or mid-reset — must
  // not be signable-into, and must not throw either.
  if (!reader.hash || !reader.salt) {
    await burnTime(password)
    return { ok: false, reason: 'invalid_credentials' }
  }

  const valid = await verifyPassword(password, { hash: reader.hash, salt: reader.salt })
  if (!valid) {
    const attempts = reader.loginAttempts + 1
    const lockUntil =
      attempts >= lockout.maxAttempts
        ? new Date(now().getTime() + lockout.lockMinutes * 60_000)
        : null
    await store.recordFailedAttempt(reader.id, lockUntil)
    return { ok: false, reason: lockUntil ? 'locked' : 'invalid_credentials' }
  }

  if (!allowUnverified && !reader.emailVerifiedAt) {
    return { ok: false, reason: 'unverified' }
  }

  await store.clearFailedAttempts(reader.id, now())
  return { ok: true, reader }
}

/**
 * Hashes against a throwaway salt when there is no account to check.
 *
 * Without this, "no such address" returns in about a millisecond and "wrong
 * password" takes the full PBKDF2 25,000 rounds. That difference is trivially
 * measurable over a few requests and turns the login form into the account
 * enumeration oracle the registration form was careful not to be.
 *
 * The dummy hash must be **`PBKDF2.keylen` bytes**, not merely hex-shaped.
 * `verifyPassword` checks the decoded length and returns early on a mismatch —
 * before doing any work — so a plausible-looking short value makes this
 * function return instantly and reopens the exact hole it exists to close.
 * That is not hypothetical: the first version of this used a 64-byte value and
 * did no hashing at all. Derived from the constant rather than written out, so
 * it cannot drift if the parameters change.
 */
async function burnTime(password: string): Promise<void> {
  await verifyPassword(password, {
    hash: 'f'.repeat(PBKDF2.keylen * 2),
    salt: crypto.randomBytes(32).toString('hex'),
  })
}

// --- single-use email tokens ----------------------------------------------

export const VERIFY_TOKEN_TTL_HOURS = 24
/**
 * One hour for a reset, twenty-four for a verification.
 *
 * A reset token is the more dangerous of the two — it changes a credential,
 * and it is the one an attacker requests on someone else's behalf — so it gets
 * the shorter window. A verification link sits in an inbox until someone next
 * checks their mail, and expiring it overnight means a mail read the next
 * morning is already dead.
 */
export const RESET_TOKEN_TTL_HOURS = 1

/**
 * A token is 32 random bytes. The **secret** goes in the link; only its SHA-256
 * goes in the database.
 *
 * Plaintext tokens in a table mean a database dump is a set of live password
 * resets against every account with one outstanding. Hashing makes a dump
 * useless for that, and costs one cheap digest per lookup.
 *
 * SHA-256, not PBKDF2: this input is 256 bits of CSPRNG output, not a
 * human-chosen password, so there is nothing to brute-force and no reason to
 * pay a work factor on every verification click.
 */
export function generateEmailToken(): { secret: string; tokenHash: string } {
  const secret = crypto.randomBytes(32).toString('base64url')
  return { secret, tokenHash: hashEmailToken(secret) }
}

export function hashEmailToken(secret: string): string {
  return crypto.createHash('sha256').update(secret).digest('hex')
}

export type IssueTokenResult = { secret: string; expiresAt: Date }

export async function issueEmailToken(
  store: ReaderStore,
  identityId: string,
  kind: EmailTokenKind,
  options: { now?: () => Date; ttlHours?: number } = {},
): Promise<IssueTokenResult> {
  const now = options.now ?? (() => new Date())
  const ttlHours =
    options.ttlHours ?? (kind === 'reset_password' ? RESET_TOKEN_TTL_HOURS : VERIFY_TOKEN_TTL_HOURS)

  // Requesting a new link invalidates the old one. Two live reset tokens means
  // an old mail — possibly forwarded, possibly in a shared inbox — still works
  // after the person has already used a newer one.
  await store.deleteTokens(identityId, kind)

  const { secret, tokenHash } = generateEmailToken()
  const expiresAt = new Date(now().getTime() + ttlHours * 3_600_000)
  await store.createToken({ identityId, kind, tokenHash, expiresAt })
  return { secret, expiresAt }
}

export type ConsumeFailure = 'not_found' | 'expired' | 'already_used' | 'wrong_kind'

export type ConsumeResult =
  | { ok: true; reader: ReaderRecord }
  | { ok: false; reason: ConsumeFailure }

/**
 * Redeems a token exactly once.
 *
 * Every failure mode is distinguished here and deliberately *collapsed* by the
 * route above: "this link is no longer valid, request a new one" covers all
 * four, because telling a visitor which one they hit leaks whether a token
 * ever existed.
 */
export async function consumeEmailToken(
  store: ReaderStore,
  secret: string,
  kind: EmailTokenKind,
  options: { now?: () => Date } = {},
): Promise<ConsumeResult> {
  const now = options.now ?? (() => new Date())
  const record = await store.findTokenByHash(hashEmailToken(secret))
  if (!record) return { ok: false, reason: 'not_found' }
  if (record.kind !== kind) return { ok: false, reason: 'wrong_kind' }
  if (record.consumedAt) return { ok: false, reason: 'already_used' }
  if (record.expiresAt.getTime() <= now().getTime()) return { ok: false, reason: 'expired' }

  const reader = await store.findById(record.identityId)
  if (!reader) return { ok: false, reason: 'not_found' }

  await store.consumeToken(record.id, now())
  return { ok: true, reader }
}

/**
 * Completes a reset: new credential, counters cleared, every other outstanding
 * reset token for that person destroyed.
 *
 * The address is also marked verified. Following a link sent to it and
 * proving control of the mailbox is the same evidence a verification link
 * provides, and leaving an account "reset but unverified" is a state with no
 * meaning.
 */
export async function completePasswordReset(
  store: ReaderStore,
  readerId: string,
  newPassword: string,
  options: { now?: () => Date } = {},
): Promise<PasswordCheck> {
  const check = checkPassword(newPassword)
  if (!check.ok) return check

  const now = options.now ?? (() => new Date())
  await store.setPassword(readerId, await hashPassword(newPassword))
  await store.clearFailedAttempts(readerId, now())
  await store.markEmailVerified(readerId, now())
  await store.deleteTokens(readerId, 'reset_password')
  return { ok: true }
}
