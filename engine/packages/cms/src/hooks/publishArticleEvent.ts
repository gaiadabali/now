import type { CollectionAfterChangeHook } from 'payload'

import { publishDomainEvent } from '../lib/redis'

/**
 * afterChange hook — Articles.
 *
 * Emits `article.published` exactly once per transition into the published
 * state (draft→published or a re-publish of new content), and
 * `article.unpublished` when an editor reverts a live article to draft.
 * Payload's drafts feature (`versions.drafts: true`) stores the published
 * state in the internal `_status` column; we diff `previousDoc._status`
 * against `doc._status` rather than trying to infer intent from field
 * changes.
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
  const wasPublished = previousDoc?._status === 'published'
  const isPublished = doc._status === 'published'

  if (!isPublished && !wasPublished) {
    return doc // never left draft — nothing to announce
  }

  const event = isPublished && (!wasPublished || operation === 'create') ? 'article.published' : null
  const unpublishEvent = wasPublished && !isPublished ? 'article.unpublished' : null
  const contentChangedWhilePublished = wasPublished && isPublished ? 'article.republished' : null

  const eventName = event ?? unpublishEvent ?? contentChangedWhilePublished
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
