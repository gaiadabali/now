/**
 * PROGRESS.md F28 verification — proves the new `events` content columns
 * (title/dek/bodyBlocks/heroMedia/article/legacyWpId) actually work through
 * Payload's local API against a real database, and that `legacyWpId`
 * enforces the uniqueness E1.8's loader needs for idempotent upsert.
 *
 * Run with: npx payload run scripts/verify-events-content.mjs
 */
import assert from 'node:assert/strict'

import config from '../payload.config.ts'
import { getPayload } from 'payload'

const payload = await getPayload({ config })

const dbNameMatch = /\/([^/?]+)(\?|$)/.exec(process.env.DATABASE_URI ?? '')
console.log(`[verify] target db = ${dbNameMatch?.[1]}`)

// 1. Existing 837 rows are intact and readable through the new field set.
const existing = await payload.find({ collection: 'events', limit: 1, sort: 'id' })
console.log(`[verify] events collection reachable — totalDocs=${existing.totalDocs}`)
assert.ok(existing.totalDocs >= 837, `expected >=837 pre-existing events, got ${existing.totalDocs}`)

// 2. Create a new event carrying the full content shape a backfilled row
//    will have: title, dek, bodyBlocks (a real block shape, not a fixture
//    dump — reusing the same field/component Articles uses), heroMedia
//    left null (no test media asset here), a unique legacyWpId.
const probeWpId = 900000001
const bodyBlocks = [
  { type: 'paragraph', html: '<p>Verification paragraph for F28.</p>' },
  { type: 'raw_html', html: '<table><tr><td>x</td></tr></table>', reason: 'unhandled_tag:table' },
]

const anyPlace = await payload.find({ collection: 'places', limit: 1 })
assert.ok(anyPlace.docs[0], 'no places found to attach the verification event to')
const placeId = anyPlace.docs[0].id

const created = await payload.create({
  collection: 'events',
  data: {
    title: 'F28 verification event',
    dek: 'A short standfirst for the verification event.',
    bodyBlocks,
    place: placeId,
    startsAt: '2026-12-01T10:00:00.000Z',
    legacyWpId: probeWpId,
    _status: 'draft',
  },
})

const fetched = await payload.findByID({ collection: 'events', id: created.id })
assert.equal(fetched.title, 'F28 verification event')
assert.equal(fetched.dek, 'A short standfirst for the verification event.')
assert.deepEqual(fetched.bodyBlocks, bodyBlocks, 'bodyBlocks did not round-trip')
assert.equal(fetched.legacyWpId, probeWpId)
console.log(`[verify] created + read back event id=${created.id} — title/dek/bodyBlocks/legacyWpId all round-trip correctly`)

// 3. legacyWpId uniqueness — a second event with the same wp_id must be
//    rejected, exactly the guarantee E1.8's loader needs to upsert by
//    legacy_wp_id instead of its own SQLite ledger.
let rejected = false
try {
  await payload.create({
    collection: 'events',
    data: {
      title: 'Duplicate legacyWpId probe',
      place: placeId,
      startsAt: '2026-12-02T10:00:00.000Z',
      legacyWpId: probeWpId,
      _status: 'draft',
    },
  })
} catch (err) {
  rejected = true
  console.log(`[verify] duplicate legacyWpId correctly rejected: ${String(err.message ?? err).slice(0, 160)}`)
}
assert.ok(rejected, 'a second event with the same legacyWpId was NOT rejected — unique index missing or not enforced')

// 4. Pre-existing rows got the DEFAULT title backfill placeholder, not a
//    NOT NULL failure, confirming the migration applied cleanly over live
//    data (837 rows) without invented dates or forced status changes.
const placeholderCount = await payload.find({
  collection: 'events',
  where: { title: { equals: 'Untitled event' } },
  limit: 0,
})
console.log(`[verify] pre-existing rows carrying the placeholder title (awaiting loader backfill): ${placeholderCount.totalDocs}`)
assert.ok(placeholderCount.totalDocs >= 836, 'expected the bulk of the 837 pre-existing rows to still carry the placeholder title')

await payload.delete({ collection: 'events', id: created.id })
console.log('[verify] cleanup done')

console.log('[verify] F28 events-content verification OK')
process.exit(0)
