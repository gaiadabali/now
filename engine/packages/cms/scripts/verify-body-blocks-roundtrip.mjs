/**
 * Proves `body_blocks` round-trips a REAL E1.2 block array unmangled.
 * `test/fixtures/body-blocks.sample.json` is not hand-written — it is the
 * literal output of `now-content-clean` run over a real article from the
 * E1.1 extraction archive (wp_id 121), containing
 * heading/paragraph/image/embed/separator blocks.
 *
 * Run with: npx payload run scripts/verify-body-blocks-roundtrip.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import config from '../payload.config.ts'
import { getPayload } from 'payload'

const dirname = path.dirname(fileURLToPath(import.meta.url))
const fixturePath = path.resolve(dirname, '../test/fixtures/body-blocks.sample.json')
const bodyBlocks = JSON.parse(readFileSync(fixturePath, 'utf-8'))

console.log(`[verify] loaded fixture: ${bodyBlocks.length} blocks, types = ${[...new Set(bodyBlocks.map((b) => b.type))].join(', ')}`)

const payload = await getPayload({ config })

const created = await payload.create({
  collection: 'articles',
  data: {
    title: 'body_blocks round-trip verification',
    kind: 'article',
    bodyBlocks,
    primaryType: 'editorial',
    format: 'news',
  },
})

const fetched = await payload.findByID({ collection: 'articles', id: created.id })

// NOTE: this is a *structural* equality check, not a raw string compare.
// ARCHITECTURE.md §5 types this column `jsonb` (and so does the migration
// Payload generated — see src/migrations/*_initial_schema.ts) and Postgres
// `jsonb`, unlike `json`, normalizes object key order and whitespace on
// storage. That means `JSON.stringify(before) !== JSON.stringify(after)`
// even though every key/value pair round-trips exactly — confirmed below
// by walking every block and asserting each field individually. This is
// inherent to `jsonb` everywhere, not a Payload artifact, and does not
// constitute content loss: nothing reads body_blocks by raw byte offset,
// every consumer reads named fields.
assert.deepEqual(fetched.bodyBlocks, bodyBlocks, 'body_blocks mutated across the round trip (deep structural mismatch)')
assert.equal(fetched.bodyBlocks.length, bodyBlocks.length, 'block count changed')
for (let i = 0; i < bodyBlocks.length; i++) {
  const before = bodyBlocks[i]
  const after = fetched.bodyBlocks[i]
  assert.equal(after.type, before.type, `block[${i}].type changed`)
  for (const key of Object.keys(before)) {
    assert.deepEqual(after[key], before[key], `block[${i}].${key} changed`)
  }
}

console.log(`[verify] round trip OK — ${bodyBlocks.length} blocks, every field of every block identical before/after (article id=${created.id})`)
console.log('[verify] (jsonb reorders object keys on storage — see comment above; content is unchanged, confirmed field-by-field)')
console.log(`[verify] sample block after read-back: ${JSON.stringify(fetched.bodyBlocks[0]).slice(0, 200)}...`)

await payload.delete({ collection: 'articles', id: created.id })
console.log('[verify] cleanup done')

process.exit(0)
