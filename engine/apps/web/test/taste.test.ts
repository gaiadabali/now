import assert from 'node:assert/strict'
import { test } from 'node:test'

import { alphaFor, blendTaste, labelFor } from '../src/lib/taste.ts'

// ---------------------------------------------------------------------------
// alphaFor — ARCHITECTURE §10's exact numbers
// ---------------------------------------------------------------------------

test('alphaFor(0) is 0 — a brand-new reader is 100% stated_seed', () => {
  assert.equal(alphaFor(0), 0)
})

test('alphaFor(20) is 0.5 — the half-life the formula names', () => {
  assert.equal(alphaFor(20), 0.5)
})

test('alphaFor grows toward 1 as n_meaningful grows, never reaching it', () => {
  const a100 = alphaFor(100)
  assert.ok(a100 > 0.8 && a100 < 1)
})

test('alphaFor never goes negative for a defensively-passed negative count', () => {
  assert.equal(alphaFor(-5), 0)
})

// ---------------------------------------------------------------------------
// blendTaste — the three-way branch (both / stated-only / revealed-only /
// neither) and which side "dominates" for the label
// ---------------------------------------------------------------------------

test('blendTaste returns null when neither side has anything — never invent taste', () => {
  assert.equal(blendTaste(null, null, 0), null)
})

test('blendTaste with only a stated seed returns it verbatim, dominant=stated', () => {
  const result = blendTaste(null, [1, 0], 0)
  assert.deepEqual(result, { vector: [1, 0], dominant: 'stated' })
})

test('blendTaste with only revealed behaviour returns it verbatim, dominant=revealed', () => {
  const result = blendTaste([0, 1], null, 12)
  assert.deepEqual(result, { vector: [0, 1], dominant: 'revealed' })
})

test('blendTaste at n_meaningful=0 with both sides is pure stated_seed (alpha=0)', () => {
  const result = blendTaste([1, 1], [0, 0], 0)
  assert.deepEqual(result!.vector, [0, 0])
  assert.equal(result!.dominant, 'stated')
})

test('blendTaste at n_meaningful=20 (alpha=0.5) is an even mix, dominant flips to revealed', () => {
  const result = blendTaste([1, 1], [0, 0], 20)
  assert.deepEqual(result!.vector, [0.5, 0.5])
  // alpha < 0.5 is the "stated" cutoff — exactly 0.5 counts as revealed
  // having taken over, matching the doc comment ("once revealed behaviour
  // has taken over").
  assert.equal(result!.dominant, 'revealed')
})

test('blendTaste well past the half-life is dominated by revealed behaviour', () => {
  const result = blendTaste([1, 1], [0, 0], 200)
  assert.equal(result!.dominant, 'revealed')
  assert.ok(result!.vector[0] > 0.8)
})

// ---------------------------------------------------------------------------
// labelFor — the honest label, never both, never a guess
// ---------------------------------------------------------------------------

test('labelFor names the picked terms when stated dominates', () => {
  assert.equal(labelFor('stated', ['Surf', 'Wellness']), 'Because you like Surf and Wellness')
})

test('labelFor caps at two labels even with more picks', () => {
  assert.equal(labelFor('stated', ['Surf', 'Wellness', 'Nightlife']), 'Because you like Surf and Wellness')
})

test('labelFor falls back to the reading-based label when revealed dominates', () => {
  assert.equal(labelFor('revealed', ['Surf', 'Wellness']), 'Because of what you read')
})

test('labelFor falls back even when stated dominates but no label resolved', () => {
  assert.equal(labelFor('stated', []), 'Because of what you read')
})
