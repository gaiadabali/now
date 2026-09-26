import type { CollectionBeforeChangeHook } from 'payload'

import { decidePlaceReview } from './placeReviewDecision'

/**
 * `beforeChange` on `places`: only an editor or admin may approve, junk or
 * merge a place, and whoever does is stamped as `reviewedBy`. The decision
 * itself is `decidePlaceReview` (pure, unit-tested); this is the wiring.
 */
export const placeReviewGate: CollectionBeforeChangeHook = ({ data, originalDoc, operation, req }) => {
  const outcome = decidePlaceReview({
    operation: operation === 'create' ? 'create' : 'update',
    data: data ?? {},
    originalDoc,
    user: req.user,
  })
  if (!outcome.ok) throw new Error(outcome.error)
  return outcome.data
}
