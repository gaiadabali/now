/**
 * The sign-in decision, tested exhaustively against an in-memory store.
 *
 * `authenticate()` knows nothing about Postgres, which is what makes this
 * possible — and this is the file the Phase 1 plan calls the real deliverable.
 * Auth is where auth bugs live; a custom strategy replaces the best-tested
 * part of Payload with our own code, so the policy it encodes has to be
 * pinned case by case rather than smoke-tested once.
 */

import assert from 'node:assert/strict'
import { describe, it } from 'node:test'

import {
  DEFAULT_LOCKOUT,
  type IdentityStore,
  type PlatformUser,
  authenticate,
  hasAnyAccess,
  isCommerceRole,
  isEditorialRole,
  normaliseEmail,
} from '../src/identity.ts'
import { hashPassword } from '../src/password.ts'

const PASSWORD = 'a perfectly reasonable password'

async function makeUser(overrides: Partial<PlatformUser> = {}): Promise<PlatformUser> {
  const { hash, salt } = await hashPassword(PASSWORD)
  return {
    id: 1,
    email: 'editor@gaiada.com',
    name: 'Editor',
    editorialRole: 'editor',
    commerceRole: 'none',
    hash,
    salt,
    loginAttempts: 0,
    lockUntil: null,
    ...overrides,
  }
}

class FakeStore implements IdentityStore {
  users: PlatformUser[]
  failures: Array<{ userId: number; lockUntil: Date | null }> = []
  cleared: number[] = []
  throwOn: 'find' | 'record' | 'clear' | null = null

  constructor(users: PlatformUser[]) {
    this.users = users
  }

  async findByEmail(email: string): Promise<PlatformUser | null> {
    if (this.throwOn === 'find') throw new Error('connection refused')
    return this.users.find((u) => u.email === email) ?? null
  }

  async recordFailedAttempt(userId: number, lockUntil: Date | null): Promise<void> {
    if (this.throwOn === 'record') throw new Error('write failed')
    this.failures.push({ userId, lockUntil })
    const user = this.users.find((u) => u.id === userId)
    if (user) {
      user.loginAttempts += 1
      user.lockUntil = lockUntil
    }
  }

  async clearFailedAttempts(userId: number): Promise<void> {
    if (this.throwOn === 'clear') throw new Error('write failed')
    this.cleared.push(userId)
  }
}

describe('authenticate — the happy path', () => {
  it('accepts correct credentials and returns the platform role', async () => {
    const user = await makeUser({ editorialRole: 'editor', commerceRole: 'partner_manager' })
    const store = new FakeStore([user])

    const result = await authenticate('editor@gaiada.com', PASSWORD, { store })

    assert.equal(result.ok, true)
    assert.deepEqual(result.ok && result.user, {
      platformId: 1,
      email: 'editor@gaiada.com',
      name: 'Editor',
      editorialRole: 'editor',
      commerceRole: 'partner_manager',
    })
  })

  it('never returns a secret', async () => {
    const store = new FakeStore([await makeUser()])
    const result = await authenticate('editor@gaiada.com', PASSWORD, { store })
    assert.equal(result.ok, true)
    const serialised = JSON.stringify(result)
    assert.doesNotMatch(serialised, /hash|salt/i)
  })

  it('clears the failed-attempt counter on success', async () => {
    const store = new FakeStore([await makeUser({ loginAttempts: 3 })])
    await authenticate('editor@gaiada.com', PASSWORD, { store })
    assert.deepEqual(store.cleared, [1])
  })

  it('matches the address case-insensitively, as payload stores it', async () => {
    const store = new FakeStore([await makeUser()])
    const result = await authenticate('  Editor@Gaiada.COM  ', PASSWORD, { store })
    assert.equal(result.ok, true)
  })
})

describe('authenticate — failures are indistinguishable', () => {
  it('rejects a wrong password', async () => {
    const store = new FakeStore([await makeUser()])
    const result = await authenticate('editor@gaiada.com', 'not the password', { store })
    assert.deepEqual(result, { ok: false, reason: 'invalid_credentials' })
  })

  it('rejects an unknown address with the SAME reason as a wrong password', async () => {
    const store = new FakeStore([await makeUser()])
    const unknown = await authenticate('nobody@gaiada.com', PASSWORD, { store })
    const wrong = await authenticate('editor@gaiada.com', 'nope', { store })
    assert.deepEqual(unknown, wrong, 'sign-in must not be an oracle for which addresses exist')
  })

  it('does not count an attempt against a user who does not exist', async () => {
    const store = new FakeStore([await makeUser()])
    await authenticate('nobody@gaiada.com', PASSWORD, { store })
    assert.deepEqual(store.failures, [])
  })

  it('rejects a user with no credential at all', async () => {
    const store = new FakeStore([await makeUser({ hash: null, salt: null })])
    const result = await authenticate('editor@gaiada.com', PASSWORD, { store })
    assert.deepEqual(result, { ok: false, reason: 'invalid_credentials' })
  })
})

describe('authenticate — lockout', () => {
  it('locks after the configured number of attempts', async () => {
    const user = await makeUser({ loginAttempts: DEFAULT_LOCKOUT.maxAttempts - 1 })
    const store = new FakeStore([user])

    await authenticate('editor@gaiada.com', 'wrong', { store })

    const recorded = store.failures.at(-1)
    assert.ok(recorded?.lockUntil instanceof Date, 'the final attempt must set a lock')
  })

  it('does not lock before the threshold', async () => {
    const store = new FakeStore([await makeUser({ loginAttempts: 0 })])
    await authenticate('editor@gaiada.com', 'wrong', { store })
    assert.equal(store.failures.at(-1)?.lockUntil, null)
  })

  it('refuses a locked account even when the password is correct', async () => {
    const future = new Date(Date.now() + 60_000)
    const store = new FakeStore([await makeUser({ lockUntil: future })])

    const result = await authenticate('editor@gaiada.com', PASSWORD, { store })

    assert.deepEqual(result, { ok: false, reason: 'locked' })
  })

  it('lets a correct password through once the lock has expired', async () => {
    const past = new Date(Date.now() - 1_000)
    const store = new FakeStore([await makeUser({ lockUntil: past, loginAttempts: 8 })])

    const result = await authenticate('editor@gaiada.com', PASSWORD, { store })

    assert.equal(result.ok, true)
  })

  it('checks the lock against an injected clock, not wall time', async () => {
    const lockUntil = new Date('2026-01-01T12:00:00Z')
    const store = new FakeStore([await makeUser({ lockUntil })])

    const during = await authenticate('editor@gaiada.com', PASSWORD, {
      store,
      now: () => new Date('2026-01-01T11:59:59Z'),
    })
    const after = await authenticate('editor@gaiada.com', PASSWORD, {
      store,
      now: () => new Date('2026-01-01T12:00:01Z'),
    })

    assert.equal(during.ok, false)
    assert.equal(after.ok, true)
  })
})

describe('authenticate — roles', () => {
  it('refuses a role this build does not recognise rather than defaulting', async () => {
    const store = new FakeStore([await makeUser({ commerceRole: 'superuser' as never })])
    const result = await authenticate('editor@gaiada.com', PASSWORD, { store })
    assert.deepEqual(result, { ok: false, reason: 'invalid_credentials' })
  })

  it('reflects a role revoked in the platform on the next sign-in', async () => {
    const user = await makeUser({ commerceRole: 'admin' })
    const store = new FakeStore([user])

    const before = await authenticate('editor@gaiada.com', PASSWORD, { store })
    assert.equal(before.ok && before.user.commerceRole, 'admin')

    // Revoked centrally — the whole reason identity lives in one place.
    user.commerceRole = 'viewer'

    const after = await authenticate('editor@gaiada.com', PASSWORD, { store })
    assert.equal(after.ok && after.user.commerceRole, 'viewer')
  })

  it('keeps the two dimensions independent', async () => {
    // A publisher with no commercial access, and a commercial user who may
    // not publish. Both are real people; one enum could not express either.
    const publisher = await makeUser({ editorialRole: 'admin', commerceRole: 'none' })
    const commercial = await makeUser({
      id: 2,
      email: 'sales@gaiada.com',
      editorialRole: 'none',
      commerceRole: 'partner_manager',
    })
    const store = new FakeStore([publisher, commercial])

    const a = await authenticate('editor@gaiada.com', PASSWORD, { store })
    const b = await authenticate('sales@gaiada.com', PASSWORD, { store })

    assert.equal(a.ok && a.user.editorialRole, 'admin')
    assert.equal(a.ok && a.user.commerceRole, 'none')
    assert.equal(b.ok && b.user.editorialRole, 'none')
    assert.equal(b.ok && b.user.commerceRole, 'partner_manager')
  })

  it('refuses a correct password when both dimensions are none', async () => {
    const store = new FakeStore([await makeUser({ editorialRole: 'none', commerceRole: 'none' })])
    const result = await authenticate('editor@gaiada.com', PASSWORD, { store })
    assert.deepEqual(result, { ok: false, reason: 'no_access' })
  })

  it('recognises exactly the roles each surface defines', () => {
    for (const role of ['admin', 'editor', 'author', 'none']) {
      assert.equal(isEditorialRole(role), true, role)
    }
    for (const role of ['admin', 'partner_manager', 'viewer', 'none']) {
      assert.equal(isCommerceRole(role), true, role)
    }
    assert.equal(isEditorialRole('partner_manager'), false, 'vocabularies must not bleed')
    assert.equal(isCommerceRole('author'), false, 'vocabularies must not bleed')
    assert.equal(isEditorialRole(null), false)
    assert.equal(isCommerceRole(''), false)
  })

  it('hasAnyAccess is false only when both are none', () => {
    assert.equal(hasAnyAccess({ editorialRole: 'none', commerceRole: 'none' }), false)
    assert.equal(hasAnyAccess({ editorialRole: 'author', commerceRole: 'none' }), true)
    assert.equal(hasAnyAccess({ editorialRole: 'none', commerceRole: 'viewer' }), true)
  })
})

describe('authenticate — the platform being unreachable', () => {
  it('reports unavailable, never invalid_credentials', async () => {
    const store = new FakeStore([await makeUser()])
    store.throwOn = 'find'

    const result = await authenticate('editor@gaiada.com', PASSWORD, { store })

    assert.deepEqual(result, { ok: false, reason: 'unavailable' })
  })

  it('does not count a database outage as a failed attempt', async () => {
    const store = new FakeStore([await makeUser()])
    store.throwOn = 'find'
    await authenticate('editor@gaiada.com', PASSWORD, { store })
    assert.deepEqual(store.failures, [], 'an outage must not lock a blameless user out')
  })

  it('still rejects a wrong password when the attempt cannot be recorded', async () => {
    const store = new FakeStore([await makeUser()])
    store.throwOn = 'record'

    const result = await authenticate('editor@gaiada.com', 'wrong', { store })

    assert.deepEqual(result, { ok: false, reason: 'invalid_credentials' })
  })

  it('still admits a correct password when the counter cannot be cleared', async () => {
    const store = new FakeStore([await makeUser()])
    store.throwOn = 'clear'

    const result = await authenticate('editor@gaiada.com', PASSWORD, { store })

    assert.equal(result.ok, true, 'failing to clear a counter is not a reason to refuse entry')
  })
})

describe('normaliseEmail', () => {
  it('trims and lowercases, matching payload on save', () => {
    assert.equal(normaliseEmail('  Hansel@Gaiada.com '), 'hansel@gaiada.com')
  })
})
