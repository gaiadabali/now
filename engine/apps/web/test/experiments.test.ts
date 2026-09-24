import assert from 'node:assert/strict'
import { test } from 'node:test'

import { ACTIVE_EXPERIMENTS, bucketFor, railKeyWithVariant } from '../src/lib/experiments.ts'

test('bucketFor returns null with no anonId — never bucket a reader we cannot show the same variant to again', () => {
  assert.equal(bucketFor('read-next', undefined), null)
})

test('bucketFor returns null for an experiment key that is not registered', () => {
  assert.equal(bucketFor('does-not-exist', 'abc-123'), null)
})

test('bucketFor is deterministic — the same anonId always gets the same variant', () => {
  const anonId = '11111111-2222-3333-4444-555555555555'
  const first = bucketFor('read-next', anonId)
  const second = bucketFor('read-next', anonId)
  assert.equal(first, second)
  assert.ok(ACTIVE_EXPERIMENTS['read-next'].variants.includes(first!))
})

test('bucketFor spreads across variants for different anonIds (not everyone in one bucket)', () => {
  const buckets = new Set<string>()
  for (let i = 0; i < 200; i++) {
    const anonId = `00000000-0000-0000-0000-${String(i).padStart(12, '0')}`
    buckets.add(bucketFor('read-next', anonId)!)
  }
  // With 200 samples across a 2-variant experiment, seeing only one variant
  // would indicate the hash is not actually varying with the input.
  assert.equal(buckets.size, ACTIVE_EXPERIMENTS['read-next'].variants.length)
})

test('railKeyWithVariant suffixes only when a variant was assigned', () => {
  assert.equal(railKeyWithVariant('read-next', 'session-intent'), 'read-next~session-intent')
  assert.equal(railKeyWithVariant('read-next', 'control'), 'read-next~control')
  assert.equal(railKeyWithVariant('read-next', null), 'read-next')
})
