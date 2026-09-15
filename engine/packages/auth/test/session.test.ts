/**
 * Session token forgery, tampering and expiry.
 *
 * This token is a bearer credential: anyone holding a valid one is the user
 * it names. So the tests that matter are the ones that try to make an invalid
 * token look valid.
 */

import assert from 'node:assert/strict'
import { createHmac } from 'node:crypto'
import { describe, it } from 'node:test'

import {
  DEFAULT_SESSION_TTL_SECONDS,
  SESSION_COOKIE,
  issueSessionToken,
  sessionCookieOptions,
  verifySessionToken,
} from '../src/session.ts'

const SECRET = 'a-test-secret-that-is-long-enough'
const CLAIMS = {
  shadowId: 42,
  email: 'editor@gaiada.com',
  editorialRole: 'editor' as const,
  commerceRole: 'viewer' as const,
}

describe('issue and verify', () => {
  it('round-trips the claims', () => {
    const token = issueSessionToken(CLAIMS, SECRET)
    const result = verifySessionToken(token, SECRET)

    assert.equal(result.ok, true)
    if (!result.ok) return
    assert.equal(result.claims.shadowId, 42)
    assert.equal(result.claims.email, 'editor@gaiada.com')
    assert.equal(result.claims.editorialRole, 'editor')
    assert.equal(result.claims.commerceRole, 'viewer')
  })

  it('sets an expiry from the ttl', () => {
    const now = () => new Date('2026-01-01T00:00:00Z')
    const token = issueSessionToken(CLAIMS, SECRET, { ttlSeconds: 3600, now })
    const result = verifySessionToken(token, SECRET, { now })

    assert.equal(result.ok, true)
    assert.equal(result.ok && result.claims.exp, Math.floor(Date.parse('2026-01-01T01:00:00Z') / 1000))
  })
})

describe('forgery', () => {
  it('rejects a token signed with a different secret', () => {
    const token = issueSessionToken(CLAIMS, 'the-attackers-secret')
    assert.deepEqual(verifySessionToken(token, SECRET), { ok: false, reason: 'bad_signature' })
  })

  it('rejects a tampered payload', () => {
    const token = issueSessionToken(CLAIMS, SECRET)
    const [body, signature] = token.split('.')

    // Promote to admin on both dimensions, keeping the original signature.
    const forged = JSON.parse(Buffer.from(body!, 'base64url').toString('utf8'))
    forged.editorialRole = 'admin'
    forged.commerceRole = 'admin'
    const tampered = `${Buffer.from(JSON.stringify(forged)).toString('base64url')}.${signature}`

    assert.deepEqual(verifySessionToken(tampered, SECRET), { ok: false, reason: 'bad_signature' })
  })

  it('rejects a token with the signature stripped', () => {
    const token = issueSessionToken(CLAIMS, SECRET)
    const [body] = token.split('.')

    assert.equal(verifySessionToken(body!, SECRET).ok, false)
    assert.equal(verifySessionToken(`${body}.`, SECRET).ok, false)
  })

  it('rejects an empty or malformed token rather than throwing', () => {
    for (const bad of ['', '.', 'a.b.c', 'not-a-token', '..']) {
      const result = verifySessionToken(bad, SECRET)
      assert.equal(result.ok, false, `expected ${JSON.stringify(bad)} to be refused`)
    }
  })

  it('rejects a well-signed token whose payload is not the expected shape', () => {
    // Signed correctly, but the claims are junk — a caller must not read
    // `shadowId` off this and hand it to a database lookup.
    const body = Buffer.from(JSON.stringify({ hello: 'world' })).toString('base64url')
    const sig = createHmac('sha256', SECRET).update(body).digest().toString('base64url')

    assert.deepEqual(verifySessionToken(`${body}.${sig}`, SECRET), {
      ok: false,
      reason: 'malformed',
    })
  })
})

describe('expiry', () => {
  it('rejects an expired token', () => {
    const issuedAt = () => new Date('2026-01-01T00:00:00Z')
    const token = issueSessionToken(CLAIMS, SECRET, { ttlSeconds: 60, now: issuedAt })

    const later = () => new Date('2026-01-01T00:01:01Z')
    assert.deepEqual(verifySessionToken(token, SECRET, { now: later }), {
      ok: false,
      reason: 'expired',
    })
  })

  it('accepts a token one second before expiry', () => {
    const issuedAt = () => new Date('2026-01-01T00:00:00Z')
    const token = issueSessionToken(CLAIMS, SECRET, { ttlSeconds: 60, now: issuedAt })

    const later = () => new Date('2026-01-01T00:00:59Z')
    assert.equal(verifySessionToken(token, SECRET, { now: later }).ok, true)
  })

  it('checks the signature before trusting the expiry', () => {
    // A forged token claiming a far-future expiry must fail on the
    // SIGNATURE, not be accepted because its exp looks fine.
    const forged = { ...CLAIMS, exp: 9_999_999_999 }
    const body = Buffer.from(JSON.stringify(forged)).toString('base64url')
    const token = `${body}.${Buffer.from('nonsense').toString('base64url')}`

    assert.deepEqual(verifySessionToken(token, SECRET), { ok: false, reason: 'bad_signature' })
  })
})

describe('secrets and cookie', () => {
  it('refuses to sign or verify with an empty secret', () => {
    assert.throws(() => issueSessionToken(CLAIMS, ''))
    assert.throws(() => verifySessionToken('anything', ''))
  })

  it('uses a __Host- prefixed cookie with the attributes that prefix requires', () => {
    assert.match(SESSION_COOKIE, /^__Host-/)
    const options = sessionCookieOptions()
    assert.equal(options.httpOnly, true)
    assert.equal(options.secure, true, '__Host- cookies are refused by browsers without Secure')
    assert.equal(options.path, '/', '__Host- requires path /')
    assert.equal(options.sameSite, 'lax')
    assert.equal(options.maxAge, DEFAULT_SESSION_TTL_SECONDS)
  })

  it('defaults to the console tokenExpiration of eight hours', () => {
    assert.equal(DEFAULT_SESSION_TTL_SECONDS, 60 * 60 * 8)
  })
})
