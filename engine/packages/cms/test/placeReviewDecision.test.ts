import assert from 'node:assert/strict'
import { test } from 'node:test'

import { decidePlaceReview } from '../src/hooks/placeReviewDecision.ts'

/**
 * P1.6's "`author` cannot approve", as the rule the `places` collection
 * enforces for every writer (admin UI, REST, Local API, the place desk).
 */

const author = { id: 7, role: 'author' }
const editor = { id: 3, role: 'editor' }
const admin = { id: 1, role: 'admin' }
const NOW = new Date('2026-09-27T00:00:00.000Z')

const update = (data: Record<string, unknown>, originalDoc: Record<string, unknown>, user: unknown) =>
  decidePlaceReview({ operation: 'update', data, originalDoc, user, now: NOW })

test('an author cannot approve a place', () => {
  const out = update({ status: 'active' }, { status: 'pending_review' }, author)
  assert.equal(out.ok, false)
  assert.match((out as { error: string }).error, /Only an editor or admin can approve/)
})

test('an author cannot junk or merge a place either', () => {
  assert.equal(update({ status: 'junk' }, { status: 'pending_review' }, author).ok, false)
  assert.equal(update({ mergedInto: 12 }, { status: 'pending_review', mergedInto: null }, author).ok, false)
})

test('nobody signed in cannot approve', () => {
  assert.equal(update({ status: 'active' }, { status: 'pending_review' }, undefined).ok, false)
})

test('an editor approves: reviewedBy and verifiedAt are stamped', () => {
  const out = update({ status: 'active' }, { status: 'pending_review' }, editor)
  assert.deepEqual(out, { ok: true, data: { status: 'active', reviewedBy: 3, verifiedAt: NOW.toISOString() } })
})

test('an explicit verifiedAt is kept', () => {
  const out = update({ status: 'active', verifiedAt: '2026-01-01T00:00:00.000Z' }, { status: 'pending_review' }, admin)
  assert.equal(out.ok && out.data.verifiedAt, '2026-01-01T00:00:00.000Z')
})

test('an author may still edit everything else, including on an approved place', () => {
  const out = update({ status: 'active', address: 'Jl. Example 1' }, { status: 'active' }, author)
  assert.deepEqual(out, { ok: true, data: { status: 'active', address: 'Jl. Example 1' } })
  assert.equal(update({ priceBand: '$$' }, { status: 'pending_review' }, author).ok, true)
})

test('a relationship given as a populated doc is compared by id', () => {
  const out = update({ mergedInto: { id: 12 } }, { mergedInto: { id: 12 } }, author)
  assert.equal(out.ok, true)
})

test('an author creating a place files it for review instead of publishing it', () => {
  const out = decidePlaceReview({ operation: 'create', data: { status: 'active', name: 'X' }, user: author, now: NOW })
  assert.deepEqual(out, { ok: true, data: { status: 'pending_review', name: 'X' } })
})

test('a create with no user (server code) is left as asked', () => {
  const out = decidePlaceReview({ operation: 'create', data: { status: 'active' }, user: undefined, now: NOW })
  assert.deepEqual(out, { ok: true, data: { status: 'active' } })
})
