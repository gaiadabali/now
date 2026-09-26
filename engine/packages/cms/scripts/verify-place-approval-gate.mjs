/**
 * Proves the place desk's role gate is real (plan P1.6: "`author` cannot
 * approve"): an author approving, junking or merging a place is rejected by
 * src/hooks/placeReviewGate.ts; an editor approving succeeds and is stamped
 * as `reviewedBy`, with `verifiedAt` set and a version recorded.
 *
 * Needs one real editor/admin in `users` (reviewedBy is a foreign key).
 * Creates two throwaway places and deletes them. Run against a scratch
 * copy, never a live city:
 *
 *   DATABASE_URI=postgresql://…/now_bali_p1_scratch npx payload run scripts/verify-place-approval-gate.mjs
 */
import assert from 'node:assert/strict'

import config from '../payload.config.ts'
import { getPayload } from 'payload'

const payload = await getPayload({ config })

const reviewers = await payload.find({
  collection: 'users',
  where: { role: { in: ['editor', 'admin'] } },
  limit: 1,
  depth: 0,
  overrideAccess: true,
})
assert.ok(reviewers.docs.length, 'no editor/admin user to act as the reviewer')
const editor = reviewers.docs[0]
const author = { ...editor, role: 'author' }

const stamp = Date.now()
const make = (suffix) =>
  payload.create({
    collection: 'places',
    data: {
      name: `verify place gate ${suffix}`,
      slug: `verify-place-gate-${suffix}-${stamp}`,
      type: 'eat',
      subtype: 'restaurant',
      status: 'pending_review',
      source: 'editor',
    },
    depth: 0,
  })
const place = await make('a')
const other = await make('b')

async function rejected(label, data) {
  try {
    await payload.update({ collection: 'places', id: place.id, data, user: author, overrideAccess: false, depth: 0 })
  } catch (err) {
    // The gate's own words, not any failure: a broken database also throws.
    assert.match(err.message, /^Only an editor or admin can/, `rejected for the wrong reason: ${err.message}`)
    console.log(`[verify] author ${label} correctly rejected: ${err.message}`)
    return true
  }
  return false
}

try {
  assert.equal(await rejected('approve', { status: 'active' }), true, 'an author approved a place')
  assert.equal(await rejected('junk', { status: 'junk' }), true, 'an author junked a place')
  assert.equal(await rejected('merge', { mergedInto: other.id }), true, 'an author merged a place')

  const fixed = await payload.update({
    collection: 'places', id: place.id, data: { address: 'verify address' }, user: author, overrideAccess: false, depth: 0,
  })
  assert.equal(fixed.status, 'pending_review')
  console.log('[verify] author may still edit an ordinary field')

  const approved = await payload.update({
    collection: 'places', id: place.id, data: { status: 'active' }, user: editor, overrideAccess: false, depth: 0,
  })
  assert.equal(approved.status, 'active')
  assert.equal(approved.reviewedBy, editor.id)
  assert.ok(approved.verifiedAt, 'verifiedAt not stamped')
  const versions = await payload.findVersions({ collection: 'places', where: { parent: { equals: place.id } }, depth: 0 })
  const latest = versions.docs[0]?.version
  assert.equal(latest?.status, 'active')
  assert.equal(latest?.reviewedBy, editor.id)
  console.log(`[verify] editor approve OK — reviewedBy=${approved.reviewedBy}, verifiedAt=${approved.verifiedAt}, ${versions.totalDocs} version(s), newest carries the actor`)
} finally {
  await payload.delete({ collection: 'places', id: place.id, overrideAccess: true })
  await payload.delete({ collection: 'places', id: other.id, overrideAccess: true })
}
console.log('[verify] place approval gate OK — author blocked, editor allowed and stamped')
process.exit(0)
