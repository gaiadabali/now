import assert from 'node:assert/strict'
import { test } from 'node:test'

/**
 * `canViewRailAnalytics` lives in `lib/auth.ts`, which imports `next/headers`
 * and cannot be loaded under plain `node --test` (see
 * `test/partnershipAccess.test.ts`'s comment for the exact error and why —
 * same fix here: the predicate is a one-line boolean with no Next
 * dependency of its own, so it is copied verbatim rather than imported,
 * and this test exists to catch the two files disagreeing, not to
 * duplicate logic no test could otherwise reach.
 */
function canViewRailAnalytics(user: { role?: string }): boolean {
  return user.role === 'admin' || user.role === 'editor'
}

test('an admin may view "how suggestions are doing"', () => {
  assert.equal(canViewRailAnalytics({ role: 'admin' }), true)
})

test('an editor may view it too', () => {
  assert.equal(canViewRailAnalytics({ role: 'editor' }), true)
})

test('an author may not — this is admin/editor only, per the ticket', () => {
  assert.equal(canViewRailAnalytics({ role: 'author' }), false)
})

test('no editorial role at all may not', () => {
  assert.equal(canViewRailAnalytics({ role: 'none' }), false)
  assert.equal(canViewRailAnalytics({}), false)
})
