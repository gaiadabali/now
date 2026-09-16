import 'server-only'

import { cookies } from 'next/headers'

import { cityPool } from '@/lib/payload'

/**
 * Attaching a reader's anonymous history to their account (E8.5).
 *
 * Someone browses for weeks, then registers. That history is sitting in
 * `interactions` under an `anon_id`, and if nothing connects the two, their
 * brand-new account looks like a cold start **when it is not** — §10's α is
 * driven by `n_meaningful`, and a reader who has read forty articles should
 * not be treated as having read none.
 *
 * The beacon has carried the `nowb_aid` cookie since E0.4 and `user_id` has
 * been in the frozen E0.2 contract just as long. This is the join nobody could
 * write because no reader could sign in.
 *
 * ## Why this is bounded, and why that is not caution for its own sake
 *
 * An `anon_id` is a device, not a person. A shared laptop, a hotel business
 * centre, a phone handed to a friend — all of them accumulate one cookie
 * across several people. Claiming *everything* that cookie ever did would
 * attribute a stranger's reading history to a named account, which is a
 * privacy incident rather than a data win, and one that is invisible
 * afterwards because the rows now look legitimately theirs.
 *
 * So: only rows inside `STITCH_WINDOW_DAYS`, only rows with no `user_id`
 * already, and a hard `STITCH_MAX_ROWS` ceiling. A device that has been
 * shared for months contributes the recent stretch that is plausibly this
 * person, and nothing older.
 *
 * ## Why failures are swallowed
 *
 * Stitching is an enrichment. A reader signing in must not see an error
 * because a partitioned table was busy — they would have no idea what it
 * meant and no way to act on it. The sign-in has already succeeded by the
 * time this runs.
 */

/** Recent enough to plausibly be the same person on the same device. */
export const STITCH_WINDOW_DAYS = 30

/**
 * Ceiling on one stitch.
 *
 * `interactions` is RANGE-partitioned by day, so an unbounded UPDATE spans
 * every partition in the window and takes locks across all of them. It is also
 * the blast radius if the window reasoning above is ever wrong.
 */
export const STITCH_MAX_ROWS = 5_000

export type StitchResult = { stitched: number; skipped: 'no_anon_id' | 'failed' | null }

/**
 * Claims this device's recent anonymous interactions for `identityId`.
 *
 * Returns the count rather than logging it, so callers can decide whether it
 * is worth reporting. Never throws.
 */
export async function stitchAnonymousHistory(identityId: string): Promise<StitchResult> {
  let anonId: string | undefined
  try {
    anonId = (await cookies()).get('nowb_aid')?.value
  } catch {
    return { stitched: 0, skipped: 'failed' }
  }

  // No beacon cookie means no anonymous history to claim — a first-ever
  // visitor, or a browser blocking cookies. Not an error.
  if (!anonId || !isUuid(anonId)) return { stitched: 0, skipped: 'no_anon_id' }

  try {
    const { rowCount } = await cityPool().query(
      `UPDATE engine.interactions
          SET user_id = $1
        WHERE ctid IN (
              SELECT ctid
                FROM engine.interactions
               WHERE anon_id = $2
                 AND user_id IS NULL
                 AND ts >= now() - ($3 || ' days')::interval
               LIMIT $4
        )`,
      [identityId, anonId, String(STITCH_WINDOW_DAYS), STITCH_MAX_ROWS],
    )
    return { stitched: rowCount ?? 0, skipped: null }
  } catch (error) {
    // Logged without the identity or the anon id: this is an operational
    // signal, not a reason to write two identifiers into the log stream that
    // together are exactly the link we are being careful about.
    console.error('[reader] history stitch failed:', error instanceof Error ? error.message : error)
    return { stitched: 0, skipped: 'failed' }
  }
}

/** `anon_id` is a uuid column; a malformed cookie would raise rather than match nothing. */
function isUuid(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
}
