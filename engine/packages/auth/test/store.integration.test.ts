/**
 * `PostgresIdentityStore` and the shadow upsert, against real databases.
 *
 * `identity.test.ts` proves the *policy* with a fake store. This file proves
 * the two things a fake cannot: that the SQL matches the schema Payload
 * actually created, and that the shadow row lands in the city database
 * carrying a role but no credential.
 *
 * The last session's two real bugs (`f.slug` vs `f.key`, and terms living in
 * the platform database rather than the city one) were both caught only by
 * running against a real schema. Auth is the last place to skip that.
 *
 * Skips cleanly when the dev stack is not up, rather than failing.
 */

import assert from 'node:assert/strict'
import { after, before, describe, it } from 'node:test'

import type { Pool } from 'pg'

import { authenticate } from '../src/identity.ts'
import { hashPassword } from '../src/password.ts'
import { PostgresIdentityStore, createPool, upsertShadowUser } from '../src/store.ts'

const PG_PASSWORD = process.env.NOW_PG_PASSWORD ?? process.env.POSTGRES_PASSWORD ?? ''
const PG_PORT = process.env.NOW_PG_PORT ?? '15432'
const PG_USER = process.env.NOW_PG_USER ?? 'now'
const PG_HOST = process.env.NOW_PG_HOST ?? 'localhost'

const dsn = (db: string) =>
  `postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:${PG_PORT}/${db}`

// Namespaced so a failed run never collides with, or deletes, a real account.
const TEST_EMAIL = 'auth-integration-test@example.invalid'
const PASSWORD = 'an integration test password'

let platformPool: Pool
let cityPool: Pool
let reachable = false

async function isReachable(pool: Pool): Promise<boolean> {
  try {
    await pool.query('SELECT 1')
    return true
  } catch {
    return false
  }
}

before(async () => {
  platformPool = createPool(dsn('now_platform'))
  cityPool = createPool(dsn('now_jakarta'))
  reachable =
    (await isReachable(platformPool)) &&
    (await isReachable(cityPool)) &&
    (await hasTwoDimensionRoles(platformPool))
})

async function hasTwoDimensionRoles(pool: Pool): Promise<boolean> {
  try {
    const { rows } = await pool.query(
      `SELECT count(*)::int AS n FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'users'
          AND column_name IN ('editorial_role', 'commerce_role')`,
    )
    return rows[0]?.n === 2
  } catch {
    return false
  }
}

after(async () => {
  if (reachable) {
    await platformPool.query('DELETE FROM public.users WHERE email = $1', [TEST_EMAIL])
    await cityPool.query('DELETE FROM public.users WHERE email = $1', [TEST_EMAIL])
  }
  await platformPool?.end()
  await cityPool?.end()
})

async function seedPlatformUser(overrides: {
  editorialRole?: string
  commerceRole?: string
  loginAttempts?: number
} = {}): Promise<number> {
  const { hash, salt } = await hashPassword(PASSWORD)
  await platformPool.query('DELETE FROM public.users WHERE email = $1', [TEST_EMAIL])
  const { rows } = await platformPool.query(
    `INSERT INTO public.users
       (email, name, editorial_role, commerce_role, hash, salt, login_attempts, updated_at, created_at)
     VALUES ($1, 'Integration Test', $2, $3, $4, $5, $6, now(), now())
     RETURNING id`,
    [
      TEST_EMAIL,
      overrides.editorialRole ?? 'editor',
      overrides.commerceRole ?? 'viewer',
      hash,
      salt,
      overrides.loginAttempts ?? 0,
    ],
  )
  return Number(rows[0].id)
}

describe('PostgresIdentityStore against the real schema', () => {
  it('reads a user payload created, including both role dimensions', async (t) => {
    if (!reachable) return t.skip('dev postgres unreachable, or migration not applied')
    await seedPlatformUser({ editorialRole: 'author', commerceRole: 'partner_manager' })

    const store = new PostgresIdentityStore(platformPool)
    const user = await store.findByEmail(TEST_EMAIL)

    assert.ok(user, 'the seeded user was not found — does the SQL match the schema?')
    assert.equal(user.editorialRole, 'author')
    assert.equal(user.commerceRole, 'partner_manager')
    assert.equal(typeof user.loginAttempts, 'number', 'numeric must not arrive as a string')
    assert.equal(user.lockUntil, null)
  })

  it('authenticates end to end against a real row', async (t) => {
    if (!reachable) return t.skip('dev postgres unreachable')
    await seedPlatformUser()
    const store = new PostgresIdentityStore(platformPool)

    const result = await authenticate(TEST_EMAIL, PASSWORD, { store })

    assert.equal(result.ok, true)
    assert.equal(result.ok && result.user.editorialRole, 'editor')
  })

  it('increments the attempt counter in the database on a wrong password', async (t) => {
    if (!reachable) return t.skip('dev postgres unreachable')
    await seedPlatformUser()
    const store = new PostgresIdentityStore(platformPool)

    await authenticate(TEST_EMAIL, 'wrong', { store })
    const after = await store.findByEmail(TEST_EMAIL)

    assert.equal(after?.loginAttempts, 1)
  })

  it('clears the counter on a correct password', async (t) => {
    if (!reachable) return t.skip('dev postgres unreachable')
    await seedPlatformUser({ loginAttempts: 5 })
    const store = new PostgresIdentityStore(platformPool)

    await authenticate(TEST_EMAIL, PASSWORD, { store })
    const after = await store.findByEmail(TEST_EMAIL)

    assert.equal(after?.loginAttempts, 0)
    assert.equal(after?.lockUntil, null)
  })

  it('persists a lock that a later read sees', async (t) => {
    if (!reachable) return t.skip('dev postgres unreachable')
    await seedPlatformUser({ loginAttempts: 7 })
    const store = new PostgresIdentityStore(platformPool)

    await authenticate(TEST_EMAIL, 'wrong', { store }) // 8th attempt
    const locked = await store.findByEmail(TEST_EMAIL)
    assert.ok(locked?.lockUntil instanceof Date, 'lock_until must round-trip as a Date')

    const result = await authenticate(TEST_EMAIL, PASSWORD, { store })
    assert.deepEqual(result, { ok: false, reason: 'locked' })
  })
})

describe('the city shadow row', () => {
  it('carries the editorial role but no credential', async (t) => {
    if (!reachable) return t.skip('dev postgres unreachable')
    await seedPlatformUser({ editorialRole: 'editor', commerceRole: 'admin' })
    const store = new PostgresIdentityStore(platformPool)
    const result = await authenticate(TEST_EMAIL, PASSWORD, { store })
    assert.equal(result.ok, true)
    if (!result.ok) return

    const shadowId = await upsertShadowUser(cityPool, result.user)

    const { rows } = await cityPool.query(
      'SELECT id, email, role, hash, salt FROM public.users WHERE id = $1',
      [shadowId],
    )
    const shadow = rows[0]
    assert.equal(shadow.email, TEST_EMAIL)
    assert.equal(shadow.role, 'editor', 'the city column takes the EDITORIAL dimension')
    assert.equal(shadow.hash, null, 'a shadow row must never carry a credential')
    assert.equal(shadow.salt, null, 'a shadow row must never carry a credential')
  })

  it('is idempotent, and refreshes the role rather than merging it', async (t) => {
    if (!reachable) return t.skip('dev postgres unreachable')
    await seedPlatformUser({ editorialRole: 'admin' })
    const store = new PostgresIdentityStore(platformPool)

    const first = await authenticate(TEST_EMAIL, PASSWORD, { store })
    assert.equal(first.ok, true)
    if (!first.ok) return
    const idA = await upsertShadowUser(cityPool, first.user)

    // Demoted centrally.
    await platformPool.query(
      `UPDATE public.users SET editorial_role = 'author' WHERE email = $1`,
      [TEST_EMAIL],
    )

    const second = await authenticate(TEST_EMAIL, PASSWORD, { store })
    assert.equal(second.ok, true)
    if (!second.ok) return
    const idB = await upsertShadowUser(cityPool, second.user)

    assert.equal(idA, idB, 'the same person must not accumulate shadow rows')

    const { rows } = await cityPool.query('SELECT role FROM public.users WHERE id = $1', [idA])
    assert.equal(rows[0].role, 'author', 'a central demotion must reach the shadow')
  })
})
