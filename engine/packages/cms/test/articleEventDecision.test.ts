import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  decideArticleEvent,
  isDraftWrite,
  type EventInputs,
} from '../src/hooks/articleEventDecision.ts'

/**
 * The regression guard for a false `article.unpublished` that reached
 * production.
 *
 * Observed 2026-09-17: opening a live article in the editor emitted
 * `article.unpublished` for it, 2.3 seconds before autosave wrote its draft,
 * while `public.articles` kept `_status=published` and its original
 * `updated_at` and the live page went on serving the full article. Payload's
 * autosave hands the hook `previousDoc._status='published'` and
 * `doc._status='draft'` without touching the live row, and the hook believed
 * the two values.
 *
 * It was harmless only because `REEMBED_EVENTS` in the one consumer that
 * exists does not include it. Nothing validates that an `article.unpublished`
 * corresponds to an article that was unpublished, so the next consumer —
 * cache invalidation, search-index removal, syndication — would have been
 * harmed by someone opening an article.
 *
 * These cases are written from Payload's own admin source rather than from a
 * guess about its internals; `articleEventDecision.ts` cites the three files.
 */

const inputs = (over: Partial<EventInputs> = {}): EventInputs => ({
  wasPublished: false,
  isPublished: false,
  operation: 'update',
  isDraftWrite: false,
  ...over,
})

// --- the bug -------------------------------------------------------------

test('autosave over a published article announces NOTHING', () => {
  // The exact shape production saw: published -> draft, but the write targeted
  // a draft so the live row never moved.
  assert.equal(
    decideArticleEvent(inputs({ wasPublished: true, isPublished: false, isDraftWrite: true })),
    null,
  )
})

test('the manual Save-draft button announces nothing either', () => {
  // Same false unpublish from a different button. Keying the fix on Payload's
  // `autosave` parameter would have fixed the first case and left this one
  // lying, which is why the discriminator is `draft`.
  assert.equal(
    decideArticleEvent(inputs({ wasPublished: true, isPublished: true, isDraftWrite: true })),
    null,
  )
  assert.equal(
    decideArticleEvent(inputs({ wasPublished: true, isPublished: false, isDraftWrite: true })),
    null,
  )
})

test('a draft write on a never-published article announces nothing', () => {
  assert.equal(decideArticleEvent(inputs({ isDraftWrite: true })), null)
})

// --- what must still work ------------------------------------------------

test('a genuine unpublish still announces itself', () => {
  // The Unpublish button sends `_status: 'draft'` with NO draft flag, which is
  // the whole basis of the distinction.
  assert.equal(
    decideArticleEvent(inputs({ wasPublished: true, isPublished: false, isDraftWrite: false })),
    'article.unpublished',
  )
})

test('publishing for the first time announces article.published', () => {
  assert.equal(
    decideArticleEvent(inputs({ wasPublished: false, isPublished: true })),
    'article.published',
  )
})

test('creating an article already published announces article.published', () => {
  // `operation === 'create'` matters: the importer creates published rows with
  // no previous state to diff against.
  assert.equal(
    decideArticleEvent(inputs({ isPublished: true, operation: 'create' })),
    'article.published',
  )
  assert.equal(
    decideArticleEvent(inputs({ wasPublished: true, isPublished: true, operation: 'create' })),
    'article.published',
  )
})

test('editing a live article announces article.republished', () => {
  assert.equal(
    decideArticleEvent(inputs({ wasPublished: true, isPublished: true })),
    'article.republished',
  )
})

test('saving a draft that was never published announces nothing', () => {
  assert.equal(decideArticleEvent(inputs()), null)
})

// --- reading the flag ----------------------------------------------------

test('the draft flag is read as the string a query parameter actually is', () => {
  // `qs` does no coercion, so this arrives as 'true', not true. Checking for
  // the boolean alone would have left the bug in place while looking fixed.
  assert.equal(isDraftWrite({ draft: 'true' }), true)
  assert.equal(isDraftWrite({ draft: true }), true, 'a Local API caller may pass the boolean')
})

test('anything else is not a draft write', () => {
  assert.equal(isDraftWrite({ draft: 'false' }), false)
  assert.equal(isDraftWrite({ draft: '' }), false)
  assert.equal(isDraftWrite({}), false)
  assert.equal(isDraftWrite(undefined), false, 'the Local API has no query at all')
  assert.equal(isDraftWrite(null), false)
  assert.equal(isDraftWrite('draft=true'), false, 'a string is not a parsed query')
  // Autosave also sends autosave=true, but keying on that is the narrower fix.
  assert.equal(isDraftWrite({ autosave: 'true' }), false)
})
