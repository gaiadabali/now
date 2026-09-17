'use server'

import { revalidatePath } from 'next/cache'

import { requireReviewerActor } from '@/lib/auth'
import { BULK_BATCH, pendingIdsForCluster, type ClusterKey } from '@/lib/review'
import { payloadClient } from '@/lib/payload'

import { clusterHref, REVIEW_ROOT } from '../../paths'

/**
 * Deciding a whole pattern at once.
 *
 * THE WRITE PATH IS THE SAME ONE A SINGLE DECISION TAKES, N TIMES. Every row
 * goes through `payload.update('classification-reviews')` with the reviewer
 * attached and `overrideAccess: false`, which means every row runs the
 * collection's hooks: `autoPopulateOnDecision` stamps `source: 'editor'` and
 * the reviewer's id, `makeApplyClassificationDecision` writes the value onto
 * the article's own field and publishes `classification.reviewed` so the
 * worker can upsert `engine.entity_terms`. There is no bulk path, and I did
 * not build one — an `UPDATE ... WHERE facet_key = $1` would have decided
 * 666 rows in nine milliseconds and told the engine about none of them, and
 * the database's own `classification_reviews_no_clobber` trigger exists
 * precisely to stop writers who think they can skip that.
 *
 * So the cost is real: roughly a tenth of a second per row, most of it the
 * article update creating a draft version. Hence the batch cap below, which
 * is the honest way to spend it.
 */

export type BulkResult =
  | { ok: true; decided: number; failed: number; remaining: number; note: string }
  | { ok: false; error: string }

/**
 * How many rows one press decides — `BULK_BATCH`, stated on the page before
 * the reviewer presses anything, so the button's promise and its behaviour
 * are the same number. See `lib/review.ts` for why it is 100.
 *
 * A background job is the right long-term answer for a 666-row cluster and is
 * deliberately not built here; there is no job runner in this app, and adding
 * one to make a button feel better would be a poor trade.
 */
const BATCH = BULK_BATCH

/**
 * How many rows are decided at once.
 *
 * Four, not one and not twenty. Each row's hooks make two writes and a Redis
 * publish on the same connection pool the page's own reads use (`max: 2` on
 * the raw pool, Payload's own beside it); at twenty, rows start waiting on
 * each other for connections and the failure mode is a pool timeout that
 * looks like a bug in the decision rather than in the concurrency. Four is
 * a four-fold speed-up that leaves the pool room to breathe.
 */
const CONCURRENCY = 4

const DECISIONS = new Set(['accepted', 'corrected', 'unclassifiable'])

function keyFrom(form: FormData): ClusterKey | null {
  const facetKey = String(form.get('facet') ?? '')
  const legacyCategory = String(form.get('legacy') ?? '')
  const proposedValue = String(form.get('value') ?? '')
  if (!facetKey || !proposedValue) return null
  return { facetKey, legacyCategory, proposedValue }
}

export async function decideCluster(
  _previous: BulkResult | null,
  form: FormData,
): Promise<BulkResult> {
  const user = await requireReviewerActor()

  const key = keyFrom(form)
  if (!key) return { ok: false, error: 'Malformed request — no cluster identified.' }

  const decision = String(form.get('decision') ?? '')
  const finalValue = String(form.get('finalValue') ?? '').trim()

  if (!DECISIONS.has(decision)) return { ok: false, error: `"${decision}" is not a review outcome.` }
  if (decision === 'corrected' && !finalValue) {
    return { ok: false, error: 'Choose the term this whole group should have been.' }
  }

  // Re-derived from the cluster key on the server, never taken from the form.
  // The client sends three strings describing a pattern; which rows that
  // pattern currently matches is this server's business, and rows a colleague
  // decided a minute ago are already gone from it.
  const ids = await pendingIdsForCluster(key, BATCH)
  if (ids.length === 0) {
    return { ok: true, decided: 0, failed: 0, remaining: 0, note: 'Nothing left pending here.' }
  }

  const payload = await payloadClient()
  const data =
    decision === 'corrected'
      ? { reviewState: 'corrected', finalValue }
      : { reviewState: decision }

  let decided = 0
  let failed = 0
  let firstError: string | null = null

  // A hand-rolled worker pool rather than `Promise.all` over the whole batch:
  // the point is the ceiling, and `Promise.all` has none.
  const queue = [...ids]
  await Promise.all(
    Array.from({ length: Math.min(CONCURRENCY, queue.length) }, async () => {
      for (let id = queue.shift(); id !== undefined; id = queue.shift()) {
        try {
          await payload.update({
            collection: 'classification-reviews',
            id,
            data,
            user,
            overrideAccess: false,
            depth: 0,
          })
          decided += 1
        } catch (err) {
          failed += 1
          // The first failure is the one worth reading — in a uniform cluster
          // the rest will say the same thing, and a hundred copies of one
          // vocabulary error is not more information.
          firstError ??= err instanceof Error ? err.message : String(err)
        }
      }
    }),
  )

  const remaining = (await pendingIdsForCluster(key, BATCH + 1)).length

  revalidatePath(clusterHref(key))
  revalidatePath(REVIEW_ROOT)

  if (decided === 0) {
    return { ok: false, error: firstError ?? 'Nothing was decided, and nothing said why.' }
  }

  return {
    ok: true,
    decided,
    failed,
    // Capped at BATCH + 1 by the lookup, so "more than a batch left" is all
    // this can honestly claim past that — the exact number is on the page
    // after it reloads.
    remaining,
    note:
      failed > 0
        ? `${decided} decided, ${failed} refused — ${firstError}`
        : `${decided} decided.`,
  }
}

export type SingleResult = { ok: true; message: string } | { ok: false; error: string }

/**
 * One row out of the cluster — the exception a reviewer spots while checking
 * the examples.
 *
 * This is the escape hatch that makes bulk safe to offer. A reviewer who sees
 * that three of the forty listed articles do not belong decides those three
 * here first; they leave `pending` and the bulk apply below, which is defined
 * as "whatever of this pattern is still undecided", no longer touches them.
 * No exclusion list, no checkbox state to get out of step with the server —
 * the ordering does the work.
 */
export async function decideOne(
  _previous: SingleResult | null,
  form: FormData,
): Promise<SingleResult> {
  const user = await requireReviewerActor()

  const key = keyFrom(form)
  const reviewId = Number(form.get('reviewId'))
  const decision = String(form.get('decision') ?? '')
  const finalValue = String(form.get('finalValue') ?? '').trim()

  if (!key || !Number.isInteger(reviewId)) {
    return { ok: false, error: 'Malformed request — no review identified.' }
  }
  if (!DECISIONS.has(decision)) return { ok: false, error: `"${decision}" is not a review outcome.` }
  if (decision === 'corrected' && !finalValue) {
    return { ok: false, error: 'Choose the term it should have been.' }
  }

  // The row must still be in the cluster the form came from. Same reasoning as
  // the per-article page's ownership check: `isReviewer` is collection-wide
  // and has no opinion about which row, so without this a crafted post could
  // decide any review in the city by number. The bound is generous because a
  // cluster is a legitimate working set, not because the check is optional.
  const inCluster = await pendingIdsForCluster(key, 10_000)
  if (!inCluster.includes(reviewId)) {
    return { ok: false, error: 'That proposal is no longer pending in this group.' }
  }

  const payload = await payloadClient()
  try {
    await payload.update({
      collection: 'classification-reviews',
      id: reviewId,
      data:
        decision === 'corrected'
          ? { reviewState: 'corrected', finalValue }
          : { reviewState: decision },
      user,
      overrideAccess: false,
      depth: 0,
    })
    revalidatePath(clusterHref(key))
    return {
      ok: true,
      message:
        decision === 'corrected' ? `Corrected to ${finalValue}.` : `Recorded as ${decision}.`,
    }
  } catch (err) {
    // Verbatim. The two realistic rejections — a term the CMS has not
    // restarted to see (F20), and the no-clobber trigger — both say exactly
    // what to do next, and paraphrasing them costs the reviewer that.
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}
