/**
 * Who may make a place-desk decision, and what gets stamped when they do.
 *
 * Plan §9.2/§12 P1.6: "every decision is a Payload version with the actor"
 * and "`author` cannot approve". Places' collection access lets any author
 * UPDATE a place, which is right for the fields a writer fixes while working
 * (an address, a price band). It is not right for three transitions that
 * decide what the public site and the itinerary engine treat as a real
 * venue:
 *
 *   - approving (`status` → `active`): the place page goes live, and the
 *     row becomes a candidate for rails and itineraries;
 *   - junking (`status` → `junk`): the row disappears from every surface;
 *   - merging (`mergedInto` set): its mentions now belong to another place.
 *
 * Those three need an editor or admin, the same people who answer for the
 * taxonomy (`canReview`, shared with the classification desk). Same shape
 * as `enforcePublishRole` for articles: the rule lives in `beforeChange`,
 * so the admin UI, REST and every Local API caller hit it alike.
 *
 * On CREATE the default status is `active`, so an author adding a venue
 * would otherwise publish it by omission. Rather than refuse the save, an
 * author's new place is filed as `pending_review` for an editor to approve.
 * A create with no user at all is server code (a seed or verify script) and
 * is left as it asked.
 *
 * When a reviewer does make one of those decisions, `reviewedBy` is stamped
 * with them (Payload's own version rows carry no actor), and an approval
 * without a `verifiedAt` gets one.
 *
 * Pure and import-free so `node --test` exercises it directly; the role
 * test below says the same thing as `canReview` in `../access` rather than
 * importing it, the way `lib/auth.ts` keeps `canReviewClassification` in step.
 */

function canReview(user: unknown): boolean {
  const role = user && typeof user === 'object' && 'role' in user ? (user as { role?: unknown }).role : null
  return role === 'admin' || role === 'editor'
}

export type PlaceReviewInput = {
  operation: 'create' | 'update'
  data: Record<string, unknown>
  originalDoc?: Record<string, unknown> | null
  user: unknown
  now?: Date
}

export type PlaceReviewOutcome =
  | { ok: true; data: Record<string, unknown> }
  | { ok: false; error: string }

function idOf(value: unknown): unknown {
  if (value && typeof value === 'object' && 'id' in value) return (value as { id: unknown }).id
  return value ?? null
}

function userId(user: unknown): unknown {
  return user && typeof user === 'object' && 'id' in user ? (user as { id: unknown }).id : null
}

export function decidePlaceReview({ operation, data, originalDoc, user, now }: PlaceReviewInput): PlaceReviewOutcome {
  const next = { ...data }
  const reviewer = canReview(user)
  const before = originalDoc ?? {}

  if (operation === 'create') {
    if (next.status === 'active' && user && !reviewer) next.status = 'pending_review'
    if (next.status === 'active' && reviewer && !next.verifiedAt) next.verifiedAt = (now ?? new Date()).toISOString()
    return { ok: true, data: next }
  }

  const approving = next.status === 'active' && before.status !== 'active'
  const junking = next.status === 'junk' && before.status !== 'junk'
  const merging =
    'mergedInto' in next && idOf(next.mergedInto) !== null && idOf(next.mergedInto) !== idOf(before.mergedInto)

  if ((approving || junking || merging) && !reviewer) {
    const what = approving ? 'approve a place' : junking ? 'mark a place as junk' : 'merge a place into another'
    return {
      ok: false,
      error: `Only an editor or admin can ${what}. Leave it as it is and an editor will decide it in the place desk.`,
    }
  }

  if (approving || junking || merging) {
    const id = userId(user)
    if (id !== null) next.reviewedBy = id
    if (approving && !next.verifiedAt) next.verifiedAt = (now ?? new Date()).toISOString()
  }
  return { ok: true, data: next }
}
