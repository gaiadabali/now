import assert from 'node:assert/strict'
import { test } from 'node:test'

import { hashPassword } from '../src/password.ts'
import {
  DEFAULT_READER_LOCKOUT,
  authenticateReader,
  checkPassword,
  completePasswordReset,
  consumeEmailToken,
  hashEmailToken,
  issueEmailToken,
  normaliseReaderEmail,
  registerReader,
} from '../src/reader.ts'
import type {
  EmailTokenKind,
  EmailTokenRecord,
  ReaderRecord,
  ReaderStore,
} from '../src/reader.ts'
import type { StoredCredential } from '../src/password.ts'

const GOOD_PASSWORD = 'a-perfectly-fine-passphrase'

/** In-memory `ReaderStore`, the seam that keeps these tests off a database. */
class FakeStore implements ReaderStore {
  readers: ReaderRecord[] = []
  tokens: (EmailTokenRecord & { tokenHash: string })[] = []
  private n = 0

  async findByEmail(emailNorm: string) {
    return this.readers.find((r) => r.emailNorm === emailNorm) ?? null
  }
  async findById(id: string) {
    return this.readers.find((r) => r.id === id) ?? null
  }
  async create(input: {
    email: string
    emailNorm: string
    name: string | null
    credential: StoredCredential
  }) {
    this.n += 1
    const reader: ReaderRecord = {
      id: `id-${this.n}`,
      email: input.email,
      emailNorm: input.emailNorm,
      name: input.name,
      hash: input.credential.hash,
      salt: input.credential.salt,
      emailVerifiedAt: null,
      loginAttempts: 0,
      lockUntil: null,
      status: 'active',
    }
    this.readers.push(reader)
    return reader
  }
  async recordFailedAttempt(id: string, lockUntil: Date | null) {
    const r = await this.findById(id)
    if (r) {
      r.loginAttempts += 1
      r.lockUntil = lockUntil
    }
  }
  async clearFailedAttempts(id: string) {
    const r = await this.findById(id)
    if (r) {
      r.loginAttempts = 0
      r.lockUntil = null
    }
  }
  async setPassword(id: string, credential: StoredCredential) {
    const r = await this.findById(id)
    if (r) {
      r.hash = credential.hash
      r.salt = credential.salt
    }
  }
  async markEmailVerified(id: string, at: Date) {
    const r = await this.findById(id)
    if (r) r.emailVerifiedAt ??= at
  }
  async createToken(input: {
    identityId: string
    kind: EmailTokenKind
    tokenHash: string
    expiresAt: Date
  }) {
    this.n += 1
    this.tokens.push({
      id: `tok-${this.n}`,
      identityId: input.identityId,
      kind: input.kind,
      tokenHash: input.tokenHash,
      expiresAt: input.expiresAt,
      consumedAt: null,
    })
  }
  async findTokenByHash(tokenHash: string) {
    return this.tokens.find((t) => t.tokenHash === tokenHash) ?? null
  }
  async consumeToken(id: string, at: Date) {
    const t = this.tokens.find((x) => x.id === id)
    if (t && !t.consumedAt) t.consumedAt = at
  }
  async deleteTokens(identityId: string, kind: EmailTokenKind) {
    this.tokens = this.tokens.filter((t) => !(t.identityId === identityId && t.kind === kind))
  }
}

// --- password policy -------------------------------------------------------

test('passwords shorter than 12 are refused', () => {
  assert.equal(checkPassword('short').ok, false)
  assert.equal(checkPassword('elevenchars').ok, false)
  assert.equal(checkPassword('twelvechars!').ok, true)
})

test('common passwords are refused, including with a digit suffix', () => {
  for (const bad of ['password1234', 'Password123!', 'qwertyuiop12', 'jakarta12345']) {
    assert.equal(checkPassword(bad).ok, false, bad)
  }
})

test('an absurdly long password is refused rather than hashed', () => {
  assert.equal(checkPassword('a'.repeat(5000)).ok, false)
})

// --- registration ----------------------------------------------------------

test('registration normalises the address and stores both forms', async () => {
  const store = new FakeStore()
  const result = await registerReader(store, { email: '  Reader@Example.COM ', password: GOOD_PASSWORD })
  assert.equal(result.ok, true)
  assert.equal(result.ok && result.reader.emailNorm, 'reader@example.com')
  assert.equal(result.ok && result.reader.email, 'Reader@Example.COM')
})

test('case variants cannot register twice', async () => {
  const store = new FakeStore()
  await registerReader(store, { email: 'reader@example.com', password: GOOD_PASSWORD })
  const second = await registerReader(store, { email: 'READER@example.com', password: GOOD_PASSWORD })
  assert.equal(second.ok, false)
  assert.equal(!second.ok && second.reason, 'already_registered')
})

test('a weak password is refused before any row is created', async () => {
  const store = new FakeStore()
  const result = await registerReader(store, { email: 'a@b.com', password: 'short' })
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'weak_password')
  assert.equal(store.readers.length, 0)
})

test('the stored credential is never the password', async () => {
  const store = new FakeStore()
  await registerReader(store, { email: 'a@b.com', password: GOOD_PASSWORD })
  const reader = store.readers[0]!
  assert.notEqual(reader.hash, GOOD_PASSWORD)
  assert.ok(reader.salt && reader.salt.length >= 32)
  assert.ok(!JSON.stringify(reader).includes(GOOD_PASSWORD))
})

// --- sign-in ---------------------------------------------------------------

async function seeded() {
  const store = new FakeStore()
  await registerReader(store, { email: 'reader@example.com', password: GOOD_PASSWORD })
  return store
}

test('correct credentials sign in', async () => {
  const store = await seeded()
  const result = await authenticateReader(store, 'reader@example.com', GOOD_PASSWORD)
  assert.equal(result.ok, true)
})

test('a wrong password does not', async () => {
  const store = await seeded()
  const result = await authenticateReader(store, 'reader@example.com', 'wrong-but-long-enough')
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'invalid_credentials')
})

test('an unknown address gives the SAME reason as a wrong password', async () => {
  // Anything else is an account enumeration oracle on the login form.
  const store = await seeded()
  const unknown = await authenticateReader(store, 'nobody@example.com', GOOD_PASSWORD)
  const wrong = await authenticateReader(store, 'reader@example.com', 'wrong-but-long-enough')
  assert.equal(unknown.ok, false)
  assert.equal(wrong.ok, false)
  assert.equal(!unknown.ok && unknown.reason, !wrong.ok && wrong.reason)
})

test('an unknown address still costs real hashing time', async () => {
  // The timing side of the same oracle. Generous bound — this asserts that
  // the dummy verify happens at all, not a precise duration.
  const store = await seeded()
  const started = process.hrtime.bigint()
  await authenticateReader(store, 'nobody@example.com', GOOD_PASSWORD)
  const elapsedMs = Number(process.hrtime.bigint() - started) / 1e6
  assert.ok(elapsedMs > 5, `expected real work, took ${elapsedMs.toFixed(1)}ms`)
})

test('lockout engages at the policy limit', async () => {
  const store = await seeded()
  for (let i = 1; i < DEFAULT_READER_LOCKOUT.maxAttempts; i += 1) {
    const r = await authenticateReader(store, 'reader@example.com', 'wrong-but-long-enough')
    assert.equal(!r.ok && r.reason, 'invalid_credentials', `attempt ${i}`)
  }
  const final = await authenticateReader(store, 'reader@example.com', 'wrong-but-long-enough')
  assert.equal(!final.ok && final.reason, 'locked')

  // And the correct password does not get in while locked.
  const correct = await authenticateReader(store, 'reader@example.com', GOOD_PASSWORD)
  assert.equal(!correct.ok && correct.reason, 'locked')
})

test('a successful sign-in clears the attempt counter', async () => {
  const store = await seeded()
  await authenticateReader(store, 'reader@example.com', 'wrong-but-long-enough')
  assert.equal(store.readers[0]!.loginAttempts, 1)
  await authenticateReader(store, 'reader@example.com', GOOD_PASSWORD)
  assert.equal(store.readers[0]!.loginAttempts, 0)
})

test('a deleted account is indistinguishable from one that never existed', async () => {
  const store = await seeded()
  store.readers[0]!.status = 'deleted'
  const result = await authenticateReader(store, 'reader@example.com', GOOD_PASSWORD)
  assert.equal(!result.ok && result.reason, 'invalid_credentials')
})

test('a suspended account is told so', async () => {
  const store = await seeded()
  store.readers[0]!.status = 'suspended'
  const result = await authenticateReader(store, 'reader@example.com', GOOD_PASSWORD)
  assert.equal(!result.ok && result.reason, 'suspended')
})

test('an identity with no credential cannot sign in and does not throw', async () => {
  const store = await seeded()
  store.readers[0]!.hash = null
  store.readers[0]!.salt = null
  const result = await authenticateReader(store, 'reader@example.com', GOOD_PASSWORD)
  assert.equal(!result.ok && result.reason, 'invalid_credentials')
})

test('unverified sign-in is allowed by default and blockable on request', async () => {
  const store = await seeded()
  assert.equal((await authenticateReader(store, 'reader@example.com', GOOD_PASSWORD)).ok, true)
  const strict = await authenticateReader(store, 'reader@example.com', GOOD_PASSWORD, {
    allowUnverified: false,
  })
  assert.equal(!strict.ok && strict.reason, 'unverified')
})

// --- email tokens ----------------------------------------------------------

test('only the hash is stored; the secret goes in the link', async () => {
  const store = await seeded()
  const { secret } = await issueEmailToken(store, 'id-1', 'verify_email')
  const stored = store.tokens[0]!
  assert.notEqual(stored.tokenHash, secret)
  assert.equal(stored.tokenHash, hashEmailToken(secret))
  assert.ok(!JSON.stringify(store.tokens).includes(secret))
})

test('a token verifies once and only once', async () => {
  const store = await seeded()
  const { secret } = await issueEmailToken(store, 'id-1', 'verify_email')

  const first = await consumeEmailToken(store, secret, 'verify_email')
  assert.equal(first.ok, true)

  const second = await consumeEmailToken(store, secret, 'verify_email')
  assert.equal(second.ok, false)
  assert.equal(!second.ok && second.reason, 'already_used')
})

test('an expired token is refused', async () => {
  const store = await seeded()
  const { secret } = await issueEmailToken(store, 'id-1', 'reset_password', { ttlHours: 1 })
  const later = () => new Date(Date.now() + 2 * 3_600_000)
  const result = await consumeEmailToken(store, secret, 'reset_password', { now: later })
  assert.equal(!result.ok && result.reason, 'expired')
})

test('a verification token cannot be used to reset a password', async () => {
  const store = await seeded()
  const { secret } = await issueEmailToken(store, 'id-1', 'verify_email')
  const result = await consumeEmailToken(store, secret, 'reset_password')
  assert.equal(!result.ok && result.reason, 'wrong_kind')
})

test('issuing a new token invalidates the previous one of the same kind', async () => {
  const store = await seeded()
  const first = await issueEmailToken(store, 'id-1', 'reset_password')
  const second = await issueEmailToken(store, 'id-1', 'reset_password')

  const old = await consumeEmailToken(store, first.secret, 'reset_password')
  assert.equal(!old.ok && old.reason, 'not_found')
  assert.equal((await consumeEmailToken(store, second.secret, 'reset_password')).ok, true)
})

test('an unknown token secret is not_found, never a throw', async () => {
  const store = await seeded()
  const result = await consumeEmailToken(store, 'never-issued', 'verify_email')
  assert.equal(!result.ok && result.reason, 'not_found')
})

test('completing a reset changes the password, verifies the address and clears tokens', async () => {
  const store = await seeded()
  await issueEmailToken(store, 'id-1', 'reset_password')
  const NEW = 'another-fine-passphrase'

  const result = await completePasswordReset(store, 'id-1', NEW)
  assert.equal(result.ok, true)

  assert.equal((await authenticateReader(store, 'reader@example.com', NEW)).ok, true)
  assert.equal((await authenticateReader(store, 'reader@example.com', GOOD_PASSWORD)).ok, false)
  assert.ok(store.readers[0]!.emailVerifiedAt)
  assert.equal(store.tokens.length, 0)
})

test('a reset to a weak password is refused and leaves the old one working', async () => {
  const store = await seeded()
  const result = await completePasswordReset(store, 'id-1', 'short')
  assert.equal(result.ok, false)
  assert.equal((await authenticateReader(store, 'reader@example.com', GOOD_PASSWORD)).ok, true)
})

test('normaliseReaderEmail matches what migration 0007 stores', () => {
  assert.equal(normaliseReaderEmail('  Foo@Bar.COM  '), 'foo@bar.com')
})

test('a credential produced here verifies with the shared hasher', async () => {
  // Proves readers and staff really are on one hashing implementation.
  const credential = await hashPassword(GOOD_PASSWORD)
  const store = new FakeStore()
  await store.create({ email: 'a@b.com', emailNorm: 'a@b.com', name: null, credential })
  assert.equal((await authenticateReader(store, 'a@b.com', GOOD_PASSWORD)).ok, true)
})
