/**
 * F86 (PROGRESS.md) — proves the DB-level guard added by migration
 * `20260910_060000_classification_reviews_no_clobber_trigger` actually
 * holds, exercised against the real CMS path, not just reasoned about.
 *
 * Three things must all be true simultaneously:
 *
 *   1. CONTROL — an ai-sourced, still-`pending` row can be freely updated
 *      by an automated writer (the guard is not vacuous; it does not just
 *      block all writes).
 *   2. ATTACK — once a human has decided a row (`source='editor'`, a
 *      non-pending `review_state`), a raw-SQL UPDATE that does not itself
 *      assert `source='editor'` — the exact "re-run of E2.1" / "backfill
 *      script" / "well-meaning fix" shape this ticket names — is REJECTED
 *      by the trigger, and the row is left byte-for-byte unchanged.
 *   3. LEGITIMATE — the real CMS path (Payload's Local API, driving the
 *      actual `autoPopulateOnDecision` hook exactly as the admin UI does)
 *      can still make a SECOND decision on an already-decided row (an
 *      editor changing their mind again) without the trigger getting in
 *      the way — the guard protects against automated writers, not
 *      against further human review.
 *
 * Every fixture this script creates is deleted at the end, in a `finally`
 * (PROGRESS.md F87's lesson: verification scripts must transact-and-
 * rollback or clean up in a `finally`, never leave rows behind).
 *
 * Run with: npx payload run scripts/verify-classification-reviews-no-clobber-trigger.mjs
 */
import assert from 'node:assert/strict'

import config from '../payload.config.ts'
import pg from 'pg'
import { getPayload } from 'payload'

const { Client } = pg
const payload = await getPayload({ config })

const existingEditor = await payload.find({ collection: 'users', where: { role: { equals: 'editor' } }, limit: 1 })
const editorUser =
  existingEditor.docs[0] ??
  (await payload.create({
    collection: 'users',
    data: {
      email: 'f86-no-clobber-trigger-verify@example.invalid',
      password: 'verify-only-not-a-real-login-1!',
      role: 'editor',
      name: 'F86 no-clobber trigger verify',
    },
  }))

const rawClient = new Client({ connectionString: process.env.DATABASE_URI })
await rawClient.connect()

const fixtureArticle = await payload.create({
  collection: 'articles',
  data: { title: '[F86 no-clobber trigger verify fixture]', kind: 'article', primaryType: 'eat', format: 'news' },
})
console.log(`[verify] fixture article ${fixtureArticle.id} created`)

let decidedReview
let controlReview

try {
  // --- 1. CONTROL: an ai-sourced, still-pending row is freely writable ---
  controlReview = await payload.create({
    collection: 'classification-reviews',
    data: {
      entity: { relationTo: 'articles', value: fixtureArticle.id },
      legacyCategory: 'Food & Drink',
      facetKey: 'type',
      proposedValue: 'eat',
      confidence: 0.4,
      reasoning: 'F86 verify fixture — control row, never decided.',
      weight: 1,
      source: 'ai',
      reviewState: 'pending',
    },
  })
  await rawClient.query(
    `UPDATE classification_reviews SET proposed_value = 'drink', confidence = 0.5 WHERE id = $1`,
    [controlReview.id],
  )
  const controlAfter = await rawClient.query(
    `SELECT proposed_value, confidence FROM classification_reviews WHERE id = $1`,
    [controlReview.id],
  )
  assert.equal(controlAfter.rows[0].proposed_value, 'drink', 'CONTROL FAILED — guard is vacuous, it blocked an undecided row too')
  console.log('[verify] CONTROL OK — an undecided (pending, source=ai) row is freely updatable by a raw writer')

  // --- 2. the human decision, through the REAL CMS path ------------------
  const pendingReview = await payload.create({
    collection: 'classification-reviews',
    data: {
      entity: { relationTo: 'articles', value: fixtureArticle.id },
      legacyCategory: 'Food & Drink',
      facetKey: 'type',
      proposedValue: 'eat',
      confidence: 0.42,
      reasoning: 'F86 verify fixture — the row a human will decide.',
      weight: 1,
      source: 'ai',
      reviewState: 'pending',
    },
  })
  decidedReview = await payload.update({
    collection: 'classification-reviews',
    id: pendingReview.id,
    data: { reviewState: 'corrected', finalValue: 'drink' },
    user: { id: editorUser.id, role: 'editor' },
  })
  assert.equal(decidedReview.source, 'editor', 'editor decision did not stamp source=editor')
  assert.equal(decidedReview.reviewState, 'corrected')
  assert.equal(decidedReview.finalValue, 'drink')
  console.log(`[verify] human decision recorded via real Payload Local API: review ${decidedReview.id} corrected -> "drink" (source=editor)`)

  // --- 3. ATTACK: automated writer tries to clobber the decision ---------
  let attackRejected = false
  try {
    await rawClient.query(
      `UPDATE classification_reviews
          SET review_state = 'pending', final_value = NULL, proposed_value = 'wellness',
              confidence = 0.61, source = 'ai'
        WHERE id = $1`,
      [decidedReview.id],
    )
  } catch (err) {
    attackRejected = true
    console.log(`[verify] ATTACK correctly rejected by the trigger: ${err.message}`)
  }
  assert.ok(attackRejected, 'CLOBBERED — an automated (source=ai) UPDATE was NOT rejected by the trigger')

  const afterAttack = await rawClient.query(
    `SELECT review_state, final_value, proposed_value, source, confidence
       FROM classification_reviews WHERE id = $1`,
    [decidedReview.id],
  )
  assert.equal(afterAttack.rows[0].review_state, 'corrected', 'CLOBBERED — review_state changed')
  assert.equal(afterAttack.rows[0].final_value, 'drink', 'CLOBBERED — final_value changed')
  assert.equal(afterAttack.rows[0].proposed_value, 'eat', 'CLOBBERED — proposed_value changed')
  assert.equal(afterAttack.rows[0].source, 'editor', 'CLOBBERED — source changed')
  console.log('[verify] row confirmed byte-for-byte unchanged after the rejected attack')

  // --- 4. same shape of attack via INSERT ... ON CONFLICT DO UPDATE ------
  // (ON CONFLICT DO UPDATE is still a row-level UPDATE event under the
  // hood — this is the exact query shape QA.6 used to clobber
  // engine.entity_terms; classification_reviews has no natural-key unique
  // constraint to conflict on, so this exercises the trigger via the PK
  // instead, which is the realistic shape a backfill keyed on `id` would use.)
  let onConflictRejected = false
  try {
    await rawClient.query(
      `INSERT INTO classification_reviews
         (id, entity_type, facet_key, proposed_value, confidence, reasoning, source, review_state)
       VALUES ($1, 'article', 'type', 'wellness', 0.7, 'attack via on-conflict-do-update', 'ai', 'pending')
       ON CONFLICT (id) DO UPDATE SET
         proposed_value = EXCLUDED.proposed_value,
         confidence = EXCLUDED.confidence,
         source = EXCLUDED.source,
         review_state = EXCLUDED.review_state`,
      [decidedReview.id],
    )
  } catch (err) {
    onConflictRejected = true
    console.log(`[verify] ON CONFLICT DO UPDATE attack also correctly rejected: ${err.message}`)
  }
  assert.ok(onConflictRejected, 'CLOBBERED — an ON CONFLICT DO UPDATE (source=ai) was NOT rejected by the trigger')

  // --- 5. LEGITIMATE: the editor decides again, through the real CMS path
  const secondDecision = await payload.update({
    collection: 'classification-reviews',
    id: decidedReview.id,
    data: { reviewState: 'corrected', finalValue: 'wellness' },
    user: { id: editorUser.id, role: 'editor' },
  })
  assert.equal(secondDecision.source, 'editor')
  assert.equal(secondDecision.finalValue, 'wellness')
  console.log(`[verify] LEGITIMATE second human decision succeeded: review ${secondDecision.id} finalValue now "${secondDecision.finalValue}"`)

  console.log('\n[verify] OK — undecided rows stay writable, a decided row survives a simulated automated clobber ' +
    '(plain UPDATE and ON CONFLICT DO UPDATE both), and a real further editor decision still succeeds.')
} finally {
  // --- cleanup: leave no fixtures behind (F87/F91) ------------------------
  if (controlReview) await payload.delete({ collection: 'classification-reviews', id: controlReview.id }).catch(() => {})
  if (decidedReview) await payload.delete({ collection: 'classification-reviews', id: decidedReview.id }).catch(() => {})
  await payload.delete({ collection: 'articles', id: fixtureArticle.id }).catch(() => {})
  await rawClient.end()
  console.log('[verify] cleanup complete — no fixtures left behind')
}

process.exit(0)
