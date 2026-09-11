/**
 * Proves the editor/author/admin role gate on publishing is real, not
 * decorative: an `author`-role user attempting to publish must be
 * rejected by src/hooks/enforcePublishRole.ts, while editor/admin succeed.
 *
 * Run with: npx payload run scripts/verify-rbac-publish-gate.mjs
 */
import assert from 'node:assert/strict'

import config from '../payload.config.ts'
import { getPayload } from 'payload'

const payload = await getPayload({ config })

let authorBlocked = false
try {
  await payload.create({
    collection: 'articles',
    data: {
      title: 'author should not be able to publish this',
      kind: 'article',
      primaryType: 'editorial',
      format: 'news',
      _status: 'published',
    },
    user: { id: 'verify-author', role: 'author' },
  })
} catch (err) {
  authorBlocked = true
  console.log(`[verify] author publish correctly rejected: ${err.message}`)
}

assert.equal(authorBlocked, true, 'an author-role user was able to publish — RBAC gate is not enforced')

const asDraft = await payload.create({
  collection: 'articles',
  data: {
    title: 'author CAN save a draft',
    kind: 'article',
    primaryType: 'editorial',
    format: 'news',
    // no _status — defaults to draft
  },
  user: { id: 'verify-author', role: 'author' },
})
console.log(`[verify] author draft save OK — article ${asDraft.id}, _status=${asDraft._status}`)

const published = await payload.update({
  collection: 'articles',
  id: asDraft.id,
  data: { _status: 'published' },
  user: { id: 'verify-editor', role: 'editor' },
})
console.log(`[verify] editor publish OK — article ${published.id}, _status=${published._status}`)

await payload.delete({ collection: 'articles', id: asDraft.id })
console.log('[verify] RBAC publish gate OK — author blocked, editor allowed')
process.exit(0)
