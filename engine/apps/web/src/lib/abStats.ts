/**
 * Two-proportion significance test and required-sample-size calculation for
 * rail A/B experiments (the engine roadmap's "clicks per rail, plus A/B
 * tests" ticket).
 *
 * Framework-free on purpose — no `next/*`, no `pg`, no `'server-only'` —
 * for the same reason `lib/commerceAccess.ts` is: this repo's test runner is
 * plain `node --test`
 * (`test/html.test.ts`), and importing anything that pulls in `next/headers`
 * throws `ERR_MODULE_NOT_FOUND` before a single assertion runs. The actual
 * MATH here has nothing to do with Next, Postgres, or this app; it is
 * exactly the kind of pure function that deserves a unit test against known
 * textbook values rather than "looks plausible" — see
 * `test/abStats.test.ts`.
 */

/**
 * Abramowitz & Stegun 7.1.26 — the standard rational approximation to the
 * error function, accurate to |error| <= 1.5e-7. Used to build the normal
 * CDF below rather than reaching for a stats package: two functions is not
 * a dependency.
 */
function erf(x: number): number {
  const sign = x < 0 ? -1 : 1
  const ax = Math.abs(x)
  const a1 = 0.254829592
  const a2 = -0.284496736
  const a3 = 1.421413741
  const a4 = -1.453152027
  const a5 = 1.061405429
  const p = 0.3275911
  const t = 1 / (1 + p * ax)
  const y = 1 - ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-ax * ax)
  return sign * y
}

/** Standard normal CDF, Φ(z) — P(Z <= z) for Z ~ N(0,1). */
export function normalCdf(z: number): number {
  return 0.5 * (1 + erf(z / Math.SQRT2))
}

/**
 * The inverse normal CDF (quantile function) is not needed as a general
 * function here — only two fixed points ever matter for this ticket
 * (95% two-sided significance, 80% power), and they are well-known
 * constants, not worth a numerical root-finder:
 *   Φ⁻¹(0.975) = 1.959964  (two-sided α = 0.05)
 *   Φ⁻¹(0.80)  = 0.841621  (power = 0.80, i.e. β = 0.20)
 */
export const Z_ALPHA_05_TWO_SIDED = 1.959964
export const Z_POWER_80 = 0.841621

export type ZTestResult = {
  /** Observed absolute CTR of each arm. */
  rateA: number
  rateB: number
  /** The z-statistic of the pooled two-proportion test. */
  z: number
  /** Two-tailed p-value. */
  pValue: number
}

/**
 * The pooled two-proportion z-test — the standard test for "is arm B's
 * click-through rate different from arm A's", given click counts and
 * impression counts for each. Returns `null` when either arm has zero
 * impressions (a rate, and therefore a test, is undefined) — the caller
 * reports "not enough data" for that case, not a division by zero dressed
 * up as a p-value.
 */
export function twoProportionZTest(clicksA: number, impressionsA: number, clicksB: number, impressionsB: number): ZTestResult | null {
  if (impressionsA <= 0 || impressionsB <= 0) return null
  const rateA = clicksA / impressionsA
  const rateB = clicksB / impressionsB
  const pooled = (clicksA + clicksB) / (impressionsA + impressionsB)
  const se = Math.sqrt(pooled * (1 - pooled) * (1 / impressionsA + 1 / impressionsB))
  if (se === 0) {
    // Both arms identical (often both exactly 0 clicks) — no evidence of a
    // difference, and no divide-by-zero: z is 0, p is 1, honestly.
    return { rateA, rateB, z: 0, pValue: 1 }
  }
  const z = (rateB - rateA) / se
  const pValue = 2 * (1 - normalCdf(Math.abs(z)))
  return { rateA, rateB, z, pValue }
}

/**
 * Required impressions PER VARIANT to reliably detect an absolute CTR
 * difference of `minDetectableEffect` (default 0.02 — the ticket's own "a
 * 2-point difference"), at the standard 95%-confidence / 80%-power
 * convention, against a baseline click-through rate `baselineRate`.
 *
 * The standard two-proportion sample-size formula (e.g. Fleiss, *Statistical
 * Methods for Rates and Proportions*, or any intro-biostatistics text):
 *
 *   n = (z_{α/2} + z_β)² · [p₁(1−p₁) + p₂(1−p₂)] / (p₁ − p₂)²
 *
 * with p₁ = baselineRate, p₂ = baselineRate + minDetectableEffect. This is a
 * real power calculation, not a guess dressed up as one — see
 * `test/abStats.test.ts` for it checked against a published reference case.
 *
 * `baselineRate` is clamped away from the extremes (min 0.005) because a
 * baseline of exactly 0 makes the formula degenerate (needs literally 0
 * events to "detect" a 2-point rise from a rate that never happens) and
 * would under-report how much data is really needed — a rail with no clicks
 * yet gets the same floor a very-low-CTR rail would.
 */
export function requiredSampleSizePerVariant(
  baselineRate: number,
  minDetectableEffect = 0.02,
  zAlpha: number = Z_ALPHA_05_TWO_SIDED,
  zPower: number = Z_POWER_80,
): number {
  const p1 = Math.min(Math.max(baselineRate, 0.005), 0.5)
  const p2 = Math.min(p1 + Math.abs(minDetectableEffect), 0.999)
  const numerator = (zAlpha + zPower) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2))
  const denominator = (p2 - p1) ** 2
  return Math.ceil(numerator / denominator)
}
