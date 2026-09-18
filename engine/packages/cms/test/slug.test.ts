import assert from 'node:assert/strict'
import { test } from 'node:test'

import { slugField, slugify } from '../src/fields/slug.ts'

/**
 * S1.1 — the address field, and the one rule that matters about it.
 *
 * A slug is a URL. Once a story is published, every share, every inbound
 * link and everything an index has crawled points at this string, so the
 * behaviour under test is mostly *when the derivation refuses to run*. The
 * failure this guards against is not a wrong slug, it is a slug that changes
 * by itself when a sub-editor sharpens a headline.
 *
 * The hook is reached through `slugField.hooks.beforeValidate` rather than
 * imported directly, so that a refactor which stops wiring it up fails here
 * instead of passing.
 */

const hook = slugField.hooks?.beforeValidate?.[0]
assert.ok(hook, 'slugField must wire a beforeValidate hook — nothing else fills the address')

/** Enough of Payload's field-hook argument to exercise the hook. */
const run = (args: { value?: unknown; title?: unknown }): unknown =>
  (hook as (a: Record<string, unknown>) => unknown)({
    value: args.value,
    siblingData: { title: args.title },
    data: { title: args.title },
    // Present so the shape is realistic; the hook reads none of these.
    operation: 'create',
    req: {},
    field: slugField,
    collection: null,
    context: {},
    path: ['slug'],
    schemaPath: ['slug'],
    indexPath: [],
    blockData: undefined,
    previousValue: undefined,
    previousSiblingDoc: {},
    previousDoc: {},
  })

// --- slugify ---------------------------------------------------------------

test('a headline becomes the address a reader would expect', () => {
  assert.equal(slugify('The Quiet Rooms of Ubud'), 'the-quiet-rooms-of-ubud')
})

test('“&” becomes “and” rather than vanishing', () => {
  // `bar-grill` reads as a typo in a URL. This is the one substitution the
  // reader app's slugify also makes, and the two must not drift.
  assert.equal(slugify('Bar & Grill'), 'bar-and-grill')
})

test('punctuation collapses instead of doubling up separators', () => {
  assert.equal(slugify('Best   Beach Clubs, 2026 — Ranked!'), 'best-beach-clubs-2026-ranked')
})

test('the result never starts or ends with a separator', () => {
  assert.equal(slugify('—  Hello  —'), 'hello')
})

test('a title with nothing Latin in it slugifies to empty, and says so', () => {
  // Not a crash and not a guess: the caller decides what to do about it,
  // which is what the next test pins down.
  assert.equal(slugify('日本語'), '')
})

// --- the hook: when it fills ------------------------------------------------

test('an empty address is filled from the headline', () => {
  assert.equal(run({ value: undefined, title: 'The Quiet Rooms of Ubud' }), 'the-quiet-rooms-of-ubud')
})

test('a blank-but-present address is filled too', () => {
  // Payload hands back '' for a text field a writer cleared, not undefined.
  assert.equal(run({ value: '   ', title: 'A Weekend, Well Spent' }), 'a-weekend-well-spent')
})

// --- the hook: when it must NOT fill ---------------------------------------

test('an address that already exists is never re-derived', () => {
  // THE test in this file. A sub-editor retitles a live story; its URL must
  // not move, or every link anyone shared breaks.
  assert.equal(
    run({ value: 'the-quiet-rooms-of-ubud', title: 'Ubud’s Quietest Hotel Rooms, Ranked' }),
    'the-quiet-rooms-of-ubud',
  )
})

test('a legacy address backfilled by migration survives a retitle', () => {
  // The same rule, stated against the 9,201 imported articles: their slug
  // came from `legacy_permalink`, and those URLs are the traffic.
  assert.equal(
    run({ value: 'jakartas-best-italian-restaurants', title: 'Something Else Entirely' }),
    'jakartas-best-italian-restaurants',
  )
})

test('an untitled draft is left without an address rather than given an empty one', () => {
  // '' is a *value* under the unique index, so two such drafts would collide
  // with each other. undefined stays NULL, which Postgres allows many of.
  assert.equal(run({ value: undefined, title: '' }), undefined)
  assert.equal(run({ value: undefined, title: undefined }), undefined)
})

test('a title that slugifies to nothing leaves the address alone', () => {
  // `required` then asks the writer for one, which is the honest outcome —
  // better than storing '' and having the second such story fail on a
  // constraint the writer cannot see.
  assert.equal(run({ value: undefined, title: '日本語' }), undefined)
})

// --- the field contract ----------------------------------------------------

test('the field is unique and indexed, because both are load-bearing', () => {
  // unique: two stories at one address means one of them is unreachable.
  // index: `getBySlug` hits this column on every article request.
  assert.equal(slugField.unique, true)
  assert.equal(slugField.index, true)
  assert.equal(slugField.name, 'slug')
})
