import type { CollectionAfterChangeHook, CollectionBeforeChangeHook } from 'payload'

import { publishDomainEvent } from '../lib/redis'
import type { VocabularyMap } from '../lib/vocabulary'
import { optionsFor } from '../lib/vocabulary'

/**
 * Hooks for `classification-reviews` (E2.8 — see ClassificationReviews.ts
 * for the full design rationale). Split into three small, single-purpose
 * hooks rather than one large one, mirroring `enforcePublishRole.ts` /
 * `publishArticleEvent.ts`'s style of "one hook, one job".
 */

/** Only these four facets are in scope for E2.8 — ARCHITECTURE.md §6's
 * "classify: type · subtype · format · location" step, gated by E2.1's
 * confidence threshold. The remaining seven seeded facets (cuisine, vibe,
 * occasion, audience, amenities, price_band, topic) are *tagging*, a
 * separate §6 pipeline stage with its own confidence — deliberately out of
 * this ticket's scope, not an oversight. */
export const CLASSIFICATION_FACETS = ['type', 'subtype', 'format', 'location'] as const
export type ClassificationFacet = (typeof CLASSIFICATION_FACETS)[number]

/**
 * Maps (entityType, facetKey) -> the actual field name on the target
 * collection that E2.1's confidence gate ultimately writes when a proposal
 * clears the auto-apply bar, and that an editor's accept/correct here
 * writes instead when it doesn't. Built directly from the real field names
 * in Articles.ts / Places.ts (both already read as part of this ticket) —
 * not every (entityType, facetKey) combination has a target: articles have
 * no `subtype` or area/location field, and places have no `format` field.
 * Where no mapping exists, the review is still recorded and the decision
 * event still fires (below), but there is nothing to write back onto the
 * entity itself — logged, not silently dropped.
 */
const FIELD_MAP: Record<ClassificationFacet, Partial<Record<'article' | 'place', string>>> = {
  type: { article: 'primaryType', place: 'type' },
  subtype: { place: 'subtype' },
  format: { article: 'format' },
  location: { place: 'areaTerm' },
}

export function targetFieldFor(entityType: 'article' | 'place', facetKey: string): string | null {
  const forFacet = FIELD_MAP[facetKey as ClassificationFacet]
  return forFacet?.[entityType] ?? null
}

/**
 * beforeValidate — derives the denormalized `entityType` text field from
 * the polymorphic `entity` relationship's `relationTo`, so the rest of this
 * collection (and any raw SQL a reviewer runs) never has to unpack Payload's
 * `{ relationTo, value }` shape just to know "article" vs "place".
 */
export const deriveEntityType: CollectionBeforeChangeHook = ({ data }) => {
  const entity = data?.entity as { relationTo?: string; value?: unknown } | undefined
  if (entity?.relationTo === 'articles') data.entityType = 'article'
  else if (entity?.relationTo === 'places') data.entityType = 'place'
  return data
}

/**
 * beforeChange — the "one click" affordance. An editor moving `reviewState`
 * to `accepted` should not have to retype the proposed value: this hook
 * copies `proposedValue` into `finalValue` automatically. Moving to
 * `unclassifiable` for the `type` facet resolves to the seeded `unknown`
 * sentinel (F49) rather than leaving `finalValue` empty — F49 exists
 * precisely so "we don't know" has a real row to point at instead of NULL.
 * Every non-`pending` transition stamps `source: 'editor'` — ARCHITECTURE.md
 * principle: a human decision, once made, outranks the classifier's guess,
 * whether the editor typed something new (correct) or simply confirmed the
 * AI was right (accept). Both must survive a re-run equally; see
 * `applyClassificationDecision` and `scripts/verify-review-no-clobber.mjs`.
 */
export const autoPopulateOnDecision: CollectionBeforeChangeHook = ({ data, originalDoc, req }) => {
  const previousState = originalDoc?.reviewState
  const nextState = data?.reviewState

  if (!nextState || nextState === previousState) return data
  if (nextState === 'pending') return data // no legitimate path back to pending; leave as-is

  if (nextState === 'accepted' && !data.finalValue) {
    data.finalValue = data.proposedValue ?? originalDoc?.proposedValue ?? null
  }

  if (nextState === 'unclassifiable') {
    data.finalValue = data.facetKey === 'type' || originalDoc?.facetKey === 'type' ? 'unknown' : null
  }

  if (nextState === 'corrected' && !data.finalValue) {
    throw new Error('reviewState=corrected requires finalValue — what should it have been instead?')
  }

  data.source = 'editor'
  data.reviewedAt = new Date().toISOString()
  data.reviewedBy = req.user?.id ?? data.reviewedBy ?? null
  return data
}

/**
 * afterChange — closes the loop once a decision has a `finalValue`:
 *   1. Writes the value onto the real entity's field in `public` via
 *      Payload's own local API (Payload writing to a table it owns — no
 *      different from any other editor field edit).
 *   2. Announces a domain event (same transport as `publishArticleEvent.ts`)
 *      carrying `source: 'editor'` and the platform `term_id` for the
 *      FINAL value (looked up from the same in-memory vocabulary map used
 *      to build the facet `select` fields — not the `termId` field stored
 *      on this doc, which is only ever the AI's *original* proposal and
 *      would be wrong after a correction), so `engine-worker` (out of this
 *      package's scope) can upsert `engine.entity_terms` — this package
 *      NEVER writes to `engine` itself, directly or otherwise. See
 *      ClassificationReviews.ts and README.md "E2.8 review queue" for the
 *      full ownership rationale.
 *   3. Also carries `previous_term_id` when a correction changed the term,
 *      so engine-worker knows to retire the superseded `entity_terms` row
 *      for this (entity, facet) — `entity_terms` is keyed on
 *      `(entity_type, entity_id, term_id)`, so "eat" corrected to "drink"
 *      produces a NEW keyed row, not an update of the old one, unless the
 *      worker is told to clean up the old key too.
 * Runs only on the transition INTO accepted/corrected/unclassifiable (not
 * on subsequent edits to an already-decided row), same "diff previousDoc"
 * style as `publishArticleEvent.ts`. Factory-wrapped so it can close over
 * the same `vocabulary` map the collection itself was built with.
 */
export function makeApplyClassificationDecision(vocabulary: VocabularyMap): CollectionAfterChangeHook {
  return async ({ doc, previousDoc, req }) => {
    const decided = ['accepted', 'corrected', 'unclassifiable']
    if (!decided.includes(doc.reviewState) || previousDoc?.reviewState === doc.reviewState) {
      return doc
    }

    const entityType = doc.entityType as 'article' | 'place'
    // `doc.entity` is `{ relationTo, value }` for a polymorphic relationship
    // field; `value` is a raw id at depth 0 but a POPULATED document object
    // at depth > 0 (afterChange hooks receive whatever depth the triggering
    // operation used) — unwrap both shapes to a bare id either way.
    const rawEntityValue = doc.entity && typeof doc.entity === 'object' ? doc.entity.value : doc.entity
    const entityId =
      rawEntityValue && typeof rawEntityValue === 'object' ? rawEntityValue.id : rawEntityValue
    const targetField = doc.finalValue ? targetFieldFor(entityType, doc.facetKey) : null

    if (targetField && entityId) {
      try {
        await req.payload.update({
          collection: entityType === 'article' ? 'articles' : 'places',
          id: entityId,
          data: { [targetField]: doc.finalValue },
          // The review decision itself is the authorization event — an
          // editor already had to pass this collection's own access control
          // to reach this hook.
          overrideAccess: true,
        })
      } catch (err) {
        console.error(
          `[cms] classification review ${doc.id}: failed to write ${targetField}=${doc.finalValue} ` +
            `onto ${entityType} ${entityId}: ${err instanceof Error ? err.message : String(err)}`,
        )
      }
    } else if (doc.finalValue) {
      console.log(
        `[cms] classification review ${doc.id}: no target field for ${entityType}.${doc.facetKey} — ` +
          'decision recorded and announced, nothing to write back onto the entity itself.',
      )
    }

    const finalTermId = doc.finalValue
      ? (optionsFor(vocabulary, doc.facetKey).find((t) => t.value === doc.finalValue)?.termId ?? null)
      : null
    const previousTermId = doc.termId && doc.termId !== finalTermId ? doc.termId : null

    await publishDomainEvent({
      event: 'classification.reviewed',
      site_slug: process.env.SITE_SLUG ?? 'unknown',
      entity_type: entityType,
      entity_id: entityId,
      occurred_at: new Date().toISOString(),
      payload: {
        review_id: doc.id,
        facet_key: doc.facetKey,
        term_id: finalTermId,
        previous_term_id: previousTermId,
        value: doc.finalValue ?? null,
        review_state: doc.reviewState,
        source: 'editor',
        confidence: doc.reviewState === 'unclassifiable' ? null : 1,
        reviewed_by: doc.reviewedBy ?? null,
        reviewed_at: doc.reviewedAt ?? null,
      },
    })

    return doc
  }
}
