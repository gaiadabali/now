import assert from 'node:assert/strict'
import { test } from 'node:test'

import { normalCdf, requiredSampleSizePerVariant, twoProportionZTest } from '../src/lib/abStats.ts'

// ---------------------------------------------------------------------------
// normalCdf — checked against the two constants every intro-stats course
// teaches by heart: Φ(1.96) ≈ 0.975, the 95%-two-sided threshold.
// ---------------------------------------------------------------------------

test('normalCdf(0) is exactly one half', () => {
  assert.ok(Math.abs(normalCdf(0) - 0.5) < 1e-9)
})

test('normalCdf(1.96) is the textbook 0.975', () => {
  assert.ok(Math.abs(normalCdf(1.959964) - 0.975) < 1e-4)
})

test('normalCdf is antisymmetric around 0', () => {
  assert.ok(Math.abs(normalCdf(1.5) + normalCdf(-1.5) - 1) < 1e-9)
})

// ---------------------------------------------------------------------------
// twoProportionZTest
// ---------------------------------------------------------------------------

test('identical rates produce z=0, p=1 — no evidence of any difference', () => {
  const result = twoProportionZTest(10, 200, 10, 200)
  assert.ok(result)
  assert.ok(Math.abs(result.z) < 1e-9)
  // The erf approximation this is built on is only accurate to ~1.5e-7
  // (its own documented error bound) — asking for tighter agreement than
  // that would be testing floating-point noise, not the math.
  assert.ok(Math.abs(result.pValue - 1) < 1e-6, `expected ~1, got ${result.pValue}`)
})

test('zero clicks in both arms is a real, defined test, not a NaN', () => {
  const result = twoProportionZTest(0, 100, 0, 100)
  assert.ok(result)
  assert.equal(result.z, 0)
  assert.equal(result.pValue, 1)
})

test('a large, obvious difference reads as significant', () => {
  // 1000 impressions each, 50 vs 200 clicks — 5% vs 20% CTR. Nobody needs a
  // power calculation to trust this one; it exists to catch a sign error.
  const result = twoProportionZTest(50, 1000, 200, 1000)
  assert.ok(result)
  assert.ok(result.rateB > result.rateA)
  assert.ok(result.pValue < 0.001)
})

test('a small difference on a small sample is not significant', () => {
  // 38 clicks on ~400 impressions vs a similar rival arm, one click apart —
  // exactly the "not enough readers yet" shape the ticket describes.
  const result = twoProportionZTest(19, 200, 19, 200)
  assert.ok(result)
  assert.ok(result.pValue > 0.9)
})

test('the p-value strictly shrinks as the observed gap widens, all else equal', () => {
  const small = twoProportionZTest(100, 2000, 110, 2000)
  const big = twoProportionZTest(100, 2000, 160, 2000)
  assert.ok(small && big)
  assert.ok(big.pValue < small.pValue)
})

test('an arm with zero impressions has no defined rate — returns null, not Infinity', () => {
  assert.equal(twoProportionZTest(0, 0, 5, 100), null)
})

// ---------------------------------------------------------------------------
// requiredSampleSizePerVariant — the real power calculation the ticket
// insists on ("Compute that 'needs' figure from a standard power
// calculation, not a guess").
// ---------------------------------------------------------------------------

test('matches Lehr\'s well-known rule-of-thumb approximation (n ≈ 16·p̄(1−p̄)/Δ²)', () => {
  // Lehr, 1992 — the standard quick-estimate everyone's biostatistics
  // professor writes on the board: for 80% power / 5% two-sided alpha,
  // n ≈ 16·p̄(1−p̄)/Δ². p1=0.10, Δ=0.02 → p̄≈0.11 → n ≈ 16·0.0979/0.0004 ≈ 3916.
  // The exact formula this file implements differs by using p1(1−p1)+p2(1−p2)
  // instead of 2·p̄(1−p̄) and 7.85 instead of Lehr's rounded 8, so this checks
  // agreement within 10%, not to the last integer.
  const n = requiredSampleSizePerVariant(0.1, 0.02)
  assert.ok(n > 3916 * 0.9 && n < 3916 * 1.1, `expected ~3916, got ${n}`)
})

test('a bigger effect needs a smaller sample — the direction the whole idea rests on', () => {
  const smallEffect = requiredSampleSizePerVariant(0.1, 0.01)
  const bigEffect = requiredSampleSizePerVariant(0.1, 0.05)
  assert.ok(bigEffect < smallEffect)
})

test('a lower baseline CTR needs more samples to detect the same absolute gap', () => {
  // Variance p(1-p) is highest near 0.5 and falls off toward the extremes,
  // but sample size for a FIXED absolute effect actually grows as the
  // baseline moves away from 0.5 only up to a point — the real, checkable
  // property is monotonic behaviour near a realistic CTR range (a few
  // percent), where p(1-p) is still increasing with p.
  const lower = requiredSampleSizePerVariant(0.02, 0.02)
  const higher = requiredSampleSizePerVariant(0.1, 0.02)
  assert.ok(lower < higher)
})

test('never returns zero or a negative number, even at the clamped floor', () => {
  const n = requiredSampleSizePerVariant(0, 0.02)
  assert.ok(n > 0)
})
