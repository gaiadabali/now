'use server'

import { revalidatePath } from 'next/cache'

import { requireEditorialActor } from '@/lib/auth'
import { reviewIdsForArticle } from '@/lib/classification'
import { payloadClient } from '@/lib/payload'

import { classifyHref } from '../paths'

/**
 * An editor deciding one queued classification.
 *
 * THE WRITE PATH IS NOT INVENTED HERE, AND THAT IS THE WHOLE POINT.
 * E2.8 already built it, end to end, and it is the only correct one:
 *
 *   this action → `payload.update('classification-reviews')`
 *     → `autoPopulateOnDecision` (beforeChange) stamps `source: 'editor'`,
 *       `reviewedBy`, `reviewedAt`, and fills `finalValue` on accept
 *     → `makeApplyClassificationDecision` (afterChange) writes the value onto
 *       `articles.primaryType` / `.format` via the Local API, then publishes
 *       `classification.reviewed` on `now:domain-events` carrying
 *       `source: 'editor'`, the platform `term_id`, and `previous_term_id`
 *     → `engine-worker` consumes that event and upserts
 *       `engine.entity_terms` with `source = 'editor'`
 *
 * So: the page does not write `engine.entity_terms`. It cannot and must not —
 * ARCHITECTURE.md §1 principle 2 gives `engine` to Alembic and machines, and
 * the `source='editor'` row that makes a human decision permanently
 * distinguishable from a guess is written by `engine-worker`, not by anything
 * in this repository's Next app. What this action does is make the decision
 * durable in `public` and let the existing hook announce it.
 *
 * TWO THINGS I CHECKED RATHER THAN ASSUMED BEFORE WIRING THIS UP:
 *
 * 1. The last link of that chain is not built. `engine-worker` does not
 *    consume `classification.reviewed` yet — `packages/cms/README.md` says so
 *    plainly, and `scripts/verify-review-no-clobber.mjs` stands in for it with
 *    a real SQL consumer to prove the loop. Until it is, a decision made here
 *    lands correctly in `classification_reviews` and on the article's own
 *    field, and the `engine.entity_terms` row still says `ai`/`inferred`. The
 *    report says that on screen rather than implying the round trip closed.
 * 2. `public.classification_reviews` carries a `BEFORE UPDATE` trigger,
 *    `classification_reviews_no_clobber`, that rejects any update to a
 *    human-decided row which does not itself assert `source='editor'`. This
 *    action passes that only because `autoPopulateOnDecision` sets `source`
 *    on every non-pending transition. It is not a rule this code restates —
 *    it is a rule this code is subject to, and going around the hook by
 *    writing SQL would have been rejected by the database. Correctly.
 *
 * ON "this app must never write" (docs/ui-data-layer.md): that contract is
 * about the READER. `(site)` renders content and must never mutate it. These
 * routes are the admin — mounted in the same Next app beside Payload's own
 * `(payload)/api/[...slug]` handlers, which write on every save an editor
 * makes in the admin UI. This write goes through the same Local API those
 * handlers use, with `overrideAccess: false` and a real user attached, so
 * `classification-reviews`' own `access.update` (`isAuthorOrAbove`) is the
 * thing deciding whether it happens.
 */

export type DecisionResult = { ok: true; message: string } | { ok: false; error: string }

const DECISIONS = new Set(['accepted', 'corrected', 'unclassifiable'])

export async function decideReview(
  _previous: DecisionResult | null,
  form: FormData,
): Promise<DecisionResult> {
  const user = await requireEditorialActor()

  const articleId = Number(form.get('articleId'))
  const reviewId = Number(form.get('reviewId'))
  const decision = String(form.get('decision') ?? '')
  const finalValue = String(form.get('finalValue') ?? '').trim()

  if (!Number.isInteger(articleId) || !Number.isInteger(reviewId)) {
    return { ok: false, error: 'Malformed request — no review identified.' }
  }
  if (!DECISIONS.has(decision)) {
    return { ok: false, error: `"${decision}" is not a review outcome.` }
  }
  if (decision === 'corrected' && !finalValue) {
    // The hook throws on this too. Catching it here turns a 500 into a
    // sentence, and the hook stays the enforcement rather than the UI.
    return { ok: false, error: 'Choose the term it should have been.' }
  }

  // The review must belong to the article whose page submitted it. The form
  // carries both ids and a form can be edited; without this check, a crafted
  // post would let a signed-in author decide any review row in the city by
  // number. Payload's access control would allow that — `isAuthorOrAbove` is
  // collection-wide and has no opinion about which article a row is for — so
  // this is the check, and it is on the server where it counts.
  const owned = await reviewIdsForArticle(articleId)
  if (!owned.includes(reviewId)) {
    return { ok: false, error: 'That review does not belong to this article.' }
  }

  const payload = await payloadClient()

  try {
    const updated = await payload.update({
      collection: 'classification-reviews',
      id: reviewId,
      data:
        decision === 'corrected'
          ? { reviewState: 'corrected', finalValue }
          : { reviewState: decision },
      user,
      // The editor's own standing decides this, not the fact that they reached
      // the page. `requireEditorialActor` redirects a commerce-only account
      // away, but the collection is what enforces the write.
      overrideAccess: false,
      depth: 0,
    })

    revalidatePath(classifyHref(`/${articleId}`))
    revalidatePath(classifyHref())

    const value = (updated as { finalValue?: string | null }).finalValue
    return {
      ok: true,
      message:
        decision === 'unclassifiable'
          ? 'Recorded as unclassifiable.'
          : `Recorded as ${decision}${value ? `: ${value}` : ''}.`,
    }
  } catch (err) {
    // Surfaced, not swallowed. The realistic failures are the collection's own
    // vocabulary `validate` rejecting a term the CMS has not restarted to see
    // (F20), and the no-clobber trigger refusing an update — both of which an
    // editor needs to read verbatim to know what to do next.
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  }
}
