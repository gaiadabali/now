/**
 * Which domain event, if any, one write to an article should announce.
 *
 * SPLIT OUT OF THE HOOK SO IT CAN BE TESTED, because it got this wrong in
 * production and nobody could have caught it by reading the hook: the inputs
 * that distinguish the cases only exist inside a live Payload request.
 *
 * WHAT WENT WRONG. The hook diffed `previousDoc._status` against
 * `doc._status` and called `published -> draft` an unpublish. Payload's
 * autosave over a published document hands the hook exactly that shape while
 * never touching the published row — so simply opening a live article in the
 * editor announced `article.unpublished` to the engine. Observed on
 * production 2026-09-17: article 3 on one city emitted it at 06:24:38.743Z
 * while `public.articles` kept `_status=published` and its original
 * `updated_at`, and the live page went on serving the full article.
 *
 * It was harmless only because nothing listens. `REEMBED_EVENTS` in
 * `packages/embeddings/src/now_embeddings/worker.py` is exactly
 * `{article.published, article.republished, place.published,
 * place.republished}` and everything else returns `ignored:event`. So one
 * allowlist in the single consumer that happens to exist is the whole
 * protection, and nothing anywhere validates that an `article.unpublished`
 * corresponds to an article that was unpublished. now-ed put it best: the
 * event is currently harmless because nothing listens, and the next thing to
 * listen will be harmed — cache invalidation, search-index removal, the
 * syndication feed in `engine.syndications`.
 *
 * WHY IT SURFACED NOW, stated carefully because the naive reading is
 * damaging. The bug is as old as the hook. What changed on 2026-09-17 is that
 * `REDIS_URL` finally reached the web containers, so the event was delivered
 * instead of logged and dropped. Connecting a transport does not only enable
 * the events you wanted. The fix belongs in this file; the wiring is what let
 * anyone find out.
 *
 * THE DISCRIMINATOR IS `draft`, AND IT WAS MEASURED RATHER THAN GUESSED —
 * read out of Payload's own admin source, because `AfterChangeHook`'s
 * declared arguments carry no autosave flag:
 *
 *   Autosave     `?autosave=true&depth=0&draft=true&…`  changed fields
 *                 (@payloadcms/ui elements/Autosave)
 *   Save draft   `?locale=…&depth=0&…&draft=true`       `_status: 'draft'`
 *                 (elements/SaveDraftButton)
 *   Unpublish    `?depth=0&…&unpublishAllLocales=…`     `_status: 'draft'`
 *                 (elements/UnpublishButton) — NO draft flag
 *
 * So both draft-writing paths carry `draft=true` and a genuine unpublish does
 * not. Keying on `autosave` would have fixed the autosave case and left the
 * manual "Save draft" button emitting the same lie — which is why the wider
 * signal is the right one.
 */

export type ArticleEvent = 'article.published' | 'article.unpublished' | 'article.republished'

export type EventInputs = {
  /** `previousDoc._status === 'published'` */
  wasPublished: boolean
  /** `doc._status === 'published'` */
  isPublished: boolean
  operation: 'create' | 'update'
  /**
   * Did this write target a DRAFT rather than the live row?
   *
   * True for autosave and for the manual Save-draft button. When it is true
   * the published row was not touched, whatever the two `_status` values look
   * like, so there is nothing for a reader-facing consumer to act on.
   */
  isDraftWrite: boolean
}

export function decideArticleEvent(inputs: EventInputs): ArticleEvent | null {
  const { wasPublished, isPublished, operation, isDraftWrite } = inputs

  // A draft write changes nothing anybody can read. Announcing it as an
  // unpublish is the bug this function exists to prevent, and announcing it
  // as a republish would be just as wrong — the live article is unchanged.
  if (isDraftWrite) return null

  if (!isPublished && !wasPublished) return null // never left draft
  if (isPublished && (!wasPublished || operation === 'create')) return 'article.published'
  if (wasPublished && !isPublished) return 'article.unpublished'
  if (wasPublished && isPublished) return 'article.republished'
  return null
}

/**
 * Read the draft flag off a Payload request.
 *
 * A query parameter, so it arrives as the STRING `'true'` — `qs` does no
 * coercion. The boolean branch is for a Local API caller that passes
 * `draft: true` as an argument rather than a query parameter; no such caller
 * exists in this repository today (`makeApplyClassificationDecision` writes
 * the live row), and if one appears it must set this or it will re-introduce
 * the false event from a direction the query check cannot see.
 */
export function isDraftWrite(query: unknown): boolean {
  if (!query || typeof query !== 'object') return false
  const draft = (query as { draft?: unknown }).draft
  return draft === 'true' || draft === true
}
