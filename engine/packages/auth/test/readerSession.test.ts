/**
 * The property these tests exist for: a reader session must never
 * authenticate into `/team-editor`, and a staff session must never be usable
 * as a reader.
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  READER_SESSION_COOKIE,
  issueReaderToken,
  readerCookieClearOptions,
  readerCookieOptions,
  verifyReaderToken,
} from '../src/readerSession.ts'
import { SESSION_COOKIE, issueSessionToken, verifySessionToken } from '../src/session.ts'
import { encodeToken } from '../src/token.ts'

const SECRET = 'reader-secret-for-tests'
const STAFF_SECRET = 'staff-secret-for-tests'
const READER = { identityId: '11111111-2222-3333-4444-555555555555', email: 'reader@example.com' }
const STAFF = {
  shadowId: 7,
  email: 'editor@example.com',
  editorialRole: 'editor' as const,
  commerceRole: 'none' as const,
}

test('a reader token round-trips', () => {
  const token = issueReaderToken(READER, SECRET)
  const result = verifyReaderToken(token, SECRET)
  assert.equal(result.ok, true)
  assert.equal(result.ok && result.claims.identityId, READER.identityId)
  assert.equal(result.ok && result.claims.aud, 'reader')
})

// --- the isolation that matters -------------------------------------------

test('a STAFF token is refused by the reader verifier, even with the same secret', () => {
  const staffToken = issueSessionToken(STAFF, SECRET)
  const result = verifyReaderToken(staffToken, SECRET)
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'wrong_audience')
})

test('a READER token is refused by the staff verifier, even with the same secret', () => {
  const readerToken = issueReaderToken(READER, SECRET)
  const result = verifySessionToken(readerToken, SECRET)
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'wrong_audience')
})

test('a legacy staff token with no aud still verifies as staff', () => {
  // Tokens minted before E8.2 carry no audience. Rejecting them would sign
  // out every editor mid-session to add a field the cookie name implies.
  const legacy = encodeToken(
    { ...STAFF, exp: Math.floor(Date.now() / 1000) + 600 },
    STAFF_SECRET,
  )
  const result = verifySessionToken(legacy, STAFF_SECRET)
  assert.equal(result.ok, true)
})

test('a token with no aud is NOT accepted as a reader', () => {
  // The legacy allowance is one-directional. A reader token has always
  // carried `aud`, so absence can only mean staff or forgery.
  const legacy = encodeToken(
    { ...READER, exp: Math.floor(Date.now() / 1000) + 600 },
    SECRET,
  )
  const result = verifyReaderToken(legacy, SECRET)
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'wrong_audience')
})

test('the two cookies have different names', () => {
  assert.notEqual(READER_SESSION_COOKIE, SESSION_COOKIE)
  assert.equal(READER_SESSION_COOKIE, '__Host-now-reader')
})

// --- ordinary token properties --------------------------------------------

test('a token signed with another secret is rejected', () => {
  const token = issueReaderToken(READER, SECRET)
  const result = verifyReaderToken(token, 'a-different-secret')
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'bad_signature')
})

test('a tampered payload is rejected', () => {
  const token = issueReaderToken(READER, SECRET)
  const [, signature] = token.split('.')
  const forged = Buffer.from(
    JSON.stringify({ ...READER, identityId: 'someone-else', exp: 9999999999, aud: 'reader' }),
  ).toString('base64url')
  const result = verifyReaderToken(`${forged}.${signature}`, SECRET)
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'bad_signature')
})

test('an expired token is rejected', () => {
  const token = issueReaderToken(READER, SECRET, { ttlSeconds: 60 })
  const later = () => new Date(Date.now() + 120_000)
  const result = verifyReaderToken(token, SECRET, { now: later })
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'expired')
})

test('malformed input never throws', () => {
  for (const bad of ['', 'x', 'a.b.c', 'not-base64.!!!', '.']) {
    const result = verifyReaderToken(bad, SECRET)
    assert.equal(result.ok, false, JSON.stringify(bad))
  }
})

test('a token missing identityId is malformed, not accepted', () => {
  const token = encodeToken(
    { email: 'a@b.com', exp: Math.floor(Date.now() / 1000) + 600, aud: 'reader' },
    SECRET,
  )
  const result = verifyReaderToken(token, SECRET)
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'malformed')
})

test('an empty secret is refused rather than signing with nothing', () => {
  assert.throws(() => issueReaderToken(READER, ''))
  assert.throws(() => verifyReaderToken('anything', ''))
})

test('the cookie is httpOnly, secure and path-scoped for __Host-', () => {
  const options = readerCookieOptions()
  assert.equal(options.httpOnly, true)
  assert.equal(options.secure, true)
  assert.equal(options.path, '/')
  assert.equal(options.sameSite, 'lax')
})

test('clearing the cookie keeps the attributes and zeroes the age', () => {
  const clear = readerCookieClearOptions()
  assert.equal(clear.maxAge, 0)
  assert.equal(clear.path, '/')
  assert.equal(clear.secure, true)
  assert.equal(clear.httpOnly, true)
})
