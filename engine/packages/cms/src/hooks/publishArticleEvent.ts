import type { CollectionAfterChangeHook } from 'payload'

import { publishDomainEvent } from '../lib/redis'
import { decideArticleEvent, isDraftWrite } from './articleEventDecision'

/**
 * afterChange hook — Articles.
 *
 * Emits `article.published` exactly once per transition into the published
 * state (draft→published or a re-publish of new content), and
 * `article.unpublished` when an editor reverts a live article to draft.
 * Payload's drafts feature (`versions.drafts: true`) stores the published
 * state in the internal `_status` column.
 *
 * The decision of WHICH event — including the rule that a draft write
 * announces nothing at all — lives in `articleEventDecision.ts`, separately
 * and under test. It is there because diffing the two `_status` values is not
 * sufficient and shipped a false `article.unpublished` to production: see that
 * file for what went wrong, what it cost, and why the discriminator is
 * Payload's `draft` query parameter rather than its `autosave` one.
 *
 * This hook computes nothing about the article — no embeddings, no tags,
 * no facets. It only announces that a publish happened, with enough
 * identifying data for `engine-worker` to go fetch the row itself
 * (ARCHITECTURE.md: "Payload must not compute anything itself").
 */
export const publishArticleEvent: CollectionAfterChangeHook = async ({
  doc,
  previousDoc,
  operation,
  req,
}) => {
  const eventName = decideArticleEvent({
    wasPublished: previousDoc?._status === 'published',
    isPublished: doc._status === 'published',
    operation: operation === 'create' ? 'create' : 'update',
    isDraftWrite: isDraftWrite(req.query),
  })
  if (!eventName) return doc

  await publishDomainEvent({
    event: eventName,
    site_slug: process.env.SITE_SLUG ?? 'unknown',
    entity_type: 'article',
    entity_id: doc.id,
    occurred_at: new Date().toISOString(),
    payload: {
      slug: doc.legacyPermalink ?? null,
      legacy_wp_id: doc.legacyWpId ?? null,
      primary_type: doc.primaryType ?? null,
      format: doc.format ?? null,
      series_key: doc.seriesKey ?? null,
      published_at: doc.publishedAt ?? null,
      actor_id: req.user?.id ?? null,
    },
  })

  return doc
}
