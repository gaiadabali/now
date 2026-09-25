/**
 * Minimal, honest A/B bucketing (WS1, Edition 2, fourth pass, item 5).
 *
 * Two rules the owner asked for directly:
 *
 *   1. Bucketing is DETERMINISTIC per `anon_id` — the same reader sees the
 *      same variant on every page view for the life of the experiment, no
 *      state to store beyond the beacon cookie that already exists.
 *   2. Variants are DATA (`ACTIVE_EXPERIMENTS` below), not a scatter of
 *      `Math.random()` or environment-variable flags across the codebase —
 *      one registry, one place WS4's dashboard and this file both read.
 *
 * ## The beacon contract is frozen
 *
 * `engine.interactions`/`engine.impressions` have no `variant` column, and
 * adding one is a migration this ticket does not have a spec for. The
 * beacon already carries `rail` on every impression and click
 * (`data-nowb-rail`) — see `app/(site)/page.tsx` and `components/StoryCard`.
 * So the variant rides IN that value: `<rail>~<variant>`, only while an
 * experiment on that rail is active. No suffix means no experiment, which is
 * also how a reader NOT in the experiment (no `anon_id` at all — a bot, a
 * server-rendered preview, a very first request before the beacon cookie is
 * set) is told apart from one who is: `bucketFor` returns `null` for either,
 * and callers render the plain, unsuffixed rail key in that case.
 *
 * WS4's dashboard is built against exactly this convention — do not change
 * the separator or the "no suffix = no experiment" rule without telling it.
 */

import { createHash } from 'node:crypto'

export type Experiment = {
  key: string
  /** First variant is the control/baseline behaviour. */
  variants: readonly string[]
}

/**
 * The one experiment this ticket needed a mechanism for: does blending the
 * current session's reads into Read Next's order (item 3) beat the
 * unweighted subject-similarity order it replaces? `control` reproduces the
 * exact ranking Read Next has always produced; `session-intent` re-ranks the
 * SAME pool with the SAME exclusions (nothing about candidate selection
 * changes — only order, per the ticket).
 */
export const ACTIVE_EXPERIMENTS: Record<string, Experiment> = {
  'read-next': { key: 'read-next', variants: ['control', 'session-intent'] },
}

/**
 * Deterministic bucket assignment: sha256(`${experimentKey}:${anonId}`),
 * first 4 bytes as an unsigned int, modulo the variant count. Stable for
 * the life of the experiment (adding/removing a variant reshuffles
 * everyone, same as any mod-based bucketing — acceptable here because
 * `ACTIVE_EXPERIMENTS` is small and hand-edited, not resized by traffic).
 *
 * Returns `null` when there is no `anonId` to key off (never bucket a
 * reader into an experiment we cannot consistently show them again) or the
 * experiment key names nothing active.
 */
export function bucketFor(experimentKey: string, anonId: string | undefined): string | null {
  if (!anonId) return null
  const experiment = ACTIVE_EXPERIMENTS[experimentKey]
  if (!experiment || experiment.variants.length === 0) return null
  const digest = createHash('sha256').update(`${experimentKey}:${anonId}`).digest()
  const n = digest.readUInt32BE(0)
  return experiment.variants[n % experiment.variants.length]
}

/**
 * `<rail>~<variant>` while an experiment is running for that reader,
 * otherwise the bare rail key — the one place this suffix gets built, so
 * every rail encodes it identically.
 */
export function railKeyWithVariant(railKey: string, variant: string | null): string {
  return variant ? `${railKey}~${variant}` : railKey
}
