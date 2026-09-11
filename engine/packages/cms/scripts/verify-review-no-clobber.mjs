/**
 * THE acceptance-critical proof for E2.8: "a re-run of classification never
 * overwrites an editor correction."
 *
 * `engine-worker` (the real consumer of the `classification.reviewed`
 * domain event, and the real place a classifier re-run would live) does not
 * exist yet — E2.1 hasn't run, `engine/packages/taxonomy-evidence` has no
 * source files, only a cache directory. This script stands in for BOTH of
 * those, clearly labelled, using nothing but real Postgres/Redis against
 * whatever DATABASE_URI/PLATFORM_DATABASE_URI/REDIS_URL point at:
 *
 *   1. Writes a real `engine.entity_terms` row directly via raw SQL —
 *      simulating E2.1's classifier, which is the only "machine" that is
 *      ever meant to write there (ARCHITECTURE.md principle 2). This
 *      package's own runtime code (payload.config.ts, collections, hooks)
 *      NEVER does this — see reviewQueueHooks.ts and ClassificationReviews.ts.
 *   2. Drives a real editor correction through Payload's actual Local API,
 *      the exact same code path the admin UI and REST API use.
 *   3. Subscribes to the real `now:domain-events` Redis channel BEFORE the
 *      correction, and on receipt, performs the upsert `engine-worker`
 *      would perform — including the source-respecting
 *      `... WHERE entity_terms.source <> 'editor'` predicate that is the
 *      actual mechanism proving a re-run cannot clobber a human decision.
 *   4. Simulates a classifier RE-RUN attempting to overwrite that row, and
 *      a CONTROL case proving the same predicate does NOT block an
 *      ordinary ai-sourced row (i.e. the guard discriminates, it isn't
 *      vacuously blocking everything).
 *
 * Run with: npx payload run scripts/verify-review-no-clobber.mjs
 */
import assert from 'node:assert/strict'

import config from '../payload.config.ts'
import Redis from 'ioredis'
import pg from 'pg'
import { getPayload } from 'payload'

const { Client } = pg
const payload = await getPayload({ config })

// --- setup: a real editor user, and real platform-seeded term ids -------
const existingEditor = await payload.find({ collection: 'users', where: { role: { equals: 'editor' } }, limit: 1 })
const editorUser =
  existingEditor.docs[0] ??
  (await payload.create({
    collection: 'users',
    data: { email: 'e2.8-noclobber-editor@example.invalid', password: 'verify-only-not-a-real-login-1!', role: 'editor', name: 'E2.8 no-clobber verify' },
  }))

const platformClient = new Client({ connectionString: process.env.PLATFORM_DATABASE_URI })
await platformClient.connect()
const termRows = await platformClient.query(
  `SELECT t.slug, t.id FROM engine.terms t JOIN engine.facets f ON f.id = t.facet_id
    WHERE f.key = 'type' AND t.slug IN ('eat', 'drink')`,
)
await platformClient.end()
const eatTermId = termRows.rows.find((r) => r.slug === 'eat')?.id
const drinkTermId = termRows.rows.find((r) => r.slug === 'drink')?.id
assert.ok(eatTermId && drinkTermId, 'expected seeded "eat"/"drink" type terms in now_platform.engine.terms')

// A dedicated pg client to the SAME database DATABASE_URI points at (the
// city DB) — entity_terms lives in that DB's `engine` schema, not a
// separate database. This client stands in for E2.1's classifier / a
// future engine-worker, NEVER for this package's own app code.
const engineClient = new Client({ connectionString: process.env.DATABASE_URI })
await engineClient.connect()

const article = await payload.create({
  collection: 'articles',
  data: { title: '[E2.8 no-clobber verify fixture]', kind: 'article', primaryType: 'eat', format: 'news' },
})
const entityId = String(article.id)
console.log(`[verify] fixture article ${entityId} created`)

// --- 1. simulate E2.1's classifier writing a low-confidence proposal -----
await engineClient.query(
  `INSERT INTO engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence)
   VALUES ('article', $1, $2, 0.6, 'ai', 0.42)`,
  [entityId, eatTermId],
)
console.log(`[verify] engine.entity_terms seeded: article ${entityId} -> "eat" (source=ai, confidence=0.42)`)

const review = await payload.create({
  collection: 'classification-reviews',
  data: {
    entity: { relationTo: 'articles', value: article.id },
    legacyCategory: 'Food & Drink',
    facetKey: 'type',
    termId: eatTermId,
    proposedValue: 'eat',
    confidence: 0.42,
    reasoning: 'verify-review-no-clobber.mjs fixture — see script header.',
    weight: 0.6,
    source: 'ai',
    reviewState: 'pending',
  },
})
console.log(`[verify] classification-review ${review.id} created (pending)`)

// --- 2. subscribe to the real domain-events channel BEFORE correcting ---
const sub = new Redis(process.env.REDIS_URL)
await sub.subscribe('now:domain-events')
const events = []
sub.on('message', (_channel, message) => events.push(JSON.parse(message)))

// --- 3. the editor corrects "eat" -> "drink" via the real Local API ------
const corrected = await payload.update({
  collection: 'classification-reviews',
  id: review.id,
  data: { reviewState: 'corrected', finalValue: 'drink' },
  user: { id: editorUser.id, role: 'editor' },
})
assert.equal(corrected.source, 'editor', 'correction did not stamp source=editor on the review row')

const reloadedArticle = await payload.findByID({ collection: 'articles', id: article.id })
assert.equal(reloadedArticle.primaryType, 'drink', 'afterChange hook did not write the correction back onto the article')
console.log(`[verify] article ${article.id}.primaryType is now "${reloadedArticle.primaryType}" (written by the review hook)`)

await new Promise((resolve) => setTimeout(resolve, 500)) // let pub/sub deliver
const event = events.find((e) => e.event === 'classification.reviewed' && String(e.entity_id) === entityId)
assert.ok(event, 'no classification.reviewed event received over now:domain-events')
assert.equal(event.payload.source, 'editor')
assert.equal(event.payload.term_id, drinkTermId, 'event term_id should be the FINAL (corrected) term, not the originally proposed one')
assert.equal(event.payload.previous_term_id, eatTermId, 'event should carry previous_term_id so the worker can retire the superseded row')
console.log(`[verify] classification.reviewed event received: term_id=${event.payload.term_id} previous_term_id=${event.payload.previous_term_id} source=${event.payload.source}`)
await sub.quit()

// --- 4. simulate engine-worker consuming that event ----------------------
// Retire the superseded "eat" proposal (entity_terms is keyed on
// (entity_type, entity_id, term_id) — a corrected term is a NEW key, not
// an update of the old one) and upsert the new, editor-sourced row.
await engineClient.query(`DELETE FROM engine.entity_terms WHERE entity_type='article' AND entity_id=$1 AND term_id=$2`, [entityId, eatTermId])
await engineClient.query(
  `INSERT INTO engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence)
   VALUES ('article', $1, $2, 1, 'editor', 1)`,
  [entityId, drinkTermId],
)
console.log('[verify] simulated engine-worker: retired "eat" row, wrote "drink" row with source=editor')

// --- 5. simulate a classifier RE-RUN trying to overwrite the correction --
// This is the exact upsert shape engine-worker's real classifier-ingest
// path must use — PROGRESS.md F27 already established the analogous
// discipline for places.type (the E1.8 loader's upsert omits protected
// columns from its SET). Here the same intent is expressed as a
// conditional ON CONFLICT so a fresh run can still refresh an untouched
// ai-sourced row (the control case below) while never touching an
// editor-sourced one.
const rerunUpsert = `
  INSERT INTO engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence)
  VALUES ('article', $1, $2, $3, 'ai', $4)
  ON CONFLICT (entity_type, entity_id, term_id)
  DO UPDATE SET weight = EXCLUDED.weight, confidence = EXCLUDED.confidence, source = EXCLUDED.source
  WHERE entity_terms.source <> 'editor'
`
await engineClient.query(rerunUpsert, [entityId, drinkTermId, 0.8, 0.55])

const afterRerun = await engineClient.query(
  `SELECT source, confidence, weight FROM engine.entity_terms WHERE entity_type='article' AND entity_id=$1 AND term_id=$2`,
  [entityId, drinkTermId],
)
const protectedRow = afterRerun.rows[0]
assert.equal(protectedRow.source, 'editor', 'CLOBBERED — re-run overwrote the editor-sourced row\'s source')
assert.equal(Number(protectedRow.confidence), 1, 'CLOBBERED — re-run overwrote the editor-sourced row\'s confidence')
assert.equal(Number(protectedRow.weight), 1, 'CLOBBERED — re-run overwrote the editor-sourced row\'s weight')
console.log(`[verify] PROTECTED — after simulated re-run: source=${protectedRow.source} confidence=${protectedRow.confidence} weight=${protectedRow.weight} (unchanged)`)

// --- 6. control: the SAME re-run upsert against an untouched ai row ------
// Proves the WHERE clause discriminates rather than blocking everything.
const controlTermId = eatTermId // reuse "eat" as an unrelated, never-reviewed proposal
await engineClient.query(
  `INSERT INTO engine.entity_terms (entity_type, entity_id, term_id, weight, source, confidence)
   VALUES ('article', $1, $2, 0.5, 'ai', 0.3)`,
  [entityId, controlTermId],
)
await engineClient.query(rerunUpsert, [entityId, controlTermId, 0.95, 0.91])
const controlAfter = await engineClient.query(
  `SELECT source, confidence, weight FROM engine.entity_terms WHERE entity_type='article' AND entity_id=$1 AND term_id=$2`,
  [entityId, controlTermId],
)
assert.equal(controlAfter.rows[0].source, 'ai')
assert.equal(Number(controlAfter.rows[0].confidence), 0.91, 'control row should have been refreshed by the re-run — the guard should not be vacuous')
console.log(`[verify] CONTROL updated as expected — confidence now ${controlAfter.rows[0].confidence} (guard is not vacuous)`)

// --- cleanup --------------------------------------------------------------
await engineClient.query(`DELETE FROM engine.entity_terms WHERE entity_type='article' AND entity_id=$1`, [entityId])
await engineClient.end()
await payload.delete({ collection: 'classification-reviews', id: review.id })
await payload.delete({ collection: 'articles', id: article.id })

console.log('\n[verify] OK — an editor correction survives a simulated classifier re-run; an unreviewed ai row does not.')
process.exit(0)
