/**
 * Proves facet fields are constrained to the seeded taxonomy
 * (now_platform.engine.terms) and reject free-typed values, and that
 * drafts/versions actually keep history (editorial essentials).
 *
 * Run with: npx payload run scripts/verify-vocabulary.mjs
 */
import assert from 'node:assert/strict'

import config from '../payload.config.ts'
import { getPayload } from 'payload'

const payload = await getPayload({ config })

// 1) A free-typed, non-seeded value must be rejected.
let rejected = false
try {
  await payload.create({
    collection: 'articles',
    data: {
      title: 'vocabulary constraint check',
      kind: 'article',
      primaryType: 'not-a-real-seeded-type', // free-typed garbage
      format: 'news',
    },
  })
} catch (err) {
  rejected = true
  console.log(`[verify] free-typed primaryType correctly rejected: ${err.message.split('\n')[0]}`)
}
assert.equal(rejected, true, 'a non-seeded value was accepted — vocabulary is not enforced')

// 2) A real seeded slug (from now_platform.engine.terms, facet "type") must
//    be accepted.
const withSeededValue = await payload.create({
  collection: 'articles',
  data: {
    title: 'vocabulary constraint check — valid value',
    kind: 'article',
    primaryType: 'eat', // seeded type-facet slug per ARCHITECTURE.md §4 type tree
    format: 'guide',
  },
})
console.log(`[verify] seeded value "eat" accepted — article ${withSeededValue.id}`)

// 3) Versions: editing a doc creates version history, independent of the
//    drafts/publish workflow.
await payload.update({
  collection: 'articles',
  id: withSeededValue.id,
  data: { title: 'vocabulary constraint check — edited title' },
})
const versions = await payload.findVersions({ collection: 'articles', where: { parent: { equals: withSeededValue.id } } })
console.log(`[verify] version history for article ${withSeededValue.id}: ${versions.totalDocs} version(s)`)
assert.ok(versions.totalDocs >= 2, 'expected at least 2 versions (create + update)')

await payload.delete({ collection: 'articles', id: withSeededValue.id })
console.log('[verify] vocabulary + versions OK')
process.exit(0)
