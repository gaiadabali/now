import type { CollectionConfig, Endpoint } from 'payload'

import { isAuthorOrAbove, isEditorOrAbove } from '@/access'
import {
  autoPopulateOnDecision,
  CLASSIFICATION_FACETS,
  deriveEntityType,
  makeApplyClassificationDecision,
} from '@/hooks/reviewQueueHooks'
import type { VocabularyMap } from '@/lib/vocabulary'
import { optionsFor } from '@/lib/vocabulary'

/**
 * `classification-reviews` — E2.8, the review queue for E2.1's confidence
 * gate. ARCHITECTURE.md §6: "review: confidence < 0.85 -> human queue."
 * Without this surface, Hansel's "everything migrates and gets classified
 * best-effort" decision means writing unreviewed guesses straight into
 * `primary_type`/`type`, which §8.A's competitor exclusion treats as fact —
 * a commercial guarantee to paying clients. This collection is where a
 * low-confidence guess stops being a guess.
 *
 * WHERE THIS TICKET CROSSES THE `public`/`engine` SCHEMA BOUNDARY (§1
 * principle 2, this package's own README "must never create, alter or read
 * anything in `engine`"): E2.1's confidence + provenance data model
 * (`weight`, `source`, `confidence`) lives in `engine.entity_terms`, which
 * this package must never touch. Resolution, deliberately parallel to how
 * E1.6 resolved the equivalent cross-database read for the facet
 * vocabulary (see README.md "Facet vocabulary across two databases"):
 *
 *   - This collection is a real, Payload-owned `public` table — every row
 *     is a durable, human-reviewable SNAPSHOT of one low-confidence
 *     proposal (facet, proposed value, confidence, weight, source,
 *     reasoning), not a live view or a cache synced from `engine`.
 *   - Payload NEVER reads or writes `engine.entity_terms` — not even
 *     read-only, unlike the vocabulary case. There is nothing in
 *     `entity_terms` this queue needs that isn't already snapshotted here:
 *     it has no reasoning/evidence column at all (confirmed by reading the
 *     real Alembic migration, `engine/packages/db/.../0001_baseline_engine_schema.py`
 *     — only `entity_type, entity_id, term_id, weight, source, confidence,
 *     created_at`), so "why the classifier chose it" has nowhere to live
 *     in `engine` today regardless. This collection is the first place
 *     that reasoning is captured, in `public`, which this package owns.
 *   - The queue is POPULATED by whoever computes a low-confidence proposal
 *     (E2.1's classifier/engine-worker) calling Payload's REST/local API to
 *     create a row here — the same "machine announces, Payload records"
 *     shape as `publishArticleEvent.ts`, just inverted (there, Payload
 *     announces to a machine; here, a machine writes to Payload). This is
 *     the CONTRACT this ticket defines for E2.1, since nothing populates
 *     real rows yet — see `scripts/seed-review-queue.mjs`, which stands in
 *     for that not-yet-built caller and is explicitly synthetic.
 *   - When an editor decides (`src/hooks/reviewQueueHooks.ts`), Payload (a)
 *     writes the final value onto the real `articles`/`places` row — a
 *     table it already owns — and (b) announces a `classification.reviewed`
 *     domain event over the existing Redis transport, carrying
 *     `source: 'editor'` and the platform `term_id`. `engine-worker` is the
 *     one that actually upserts `engine.entity_terms` with `source='editor'`
 *     — a machine writing to `engine`, exactly per principle 2 ("machines
 *     write engine"), never Payload. This package's part of the "never
 *     overwrite an editor correction" guarantee is making that decision
 *     durable and announcing it unambiguously; `engine-worker`'s part
 *     (out of scope here) is respecting `source='editor'` on upsert, the
 *     same discipline the E1.8 loader already applies to `places.type`
 *     (PROGRESS.md F27 — its upsert omits `type/subtype/status` from `SET`
 *     for exactly this reason). `scripts/verify-review-no-clobber.mjs`
 *     proves the full loop end-to-end, standing in for `engine-worker`
 *     with a small real-SQL consumer since it does not exist yet.
 *
 * SCOPE: only the four ARCHITECTURE.md §6 CLASSIFICATION facets — type,
 * subtype, format, location — not the seven tagging facets (cuisine, vibe,
 * occasion, audience, amenities, price_band, topic), which are a separate
 * pipeline stage with their own confidence and are not this ticket's
 * "classify... (WP category = prior)" step. See reviewQueueHooks.ts.
 *
 * F20 / vocabulary-ENUM churn: `proposedValue`/`finalValue` are plain
 * `text`, deliberately NOT backed by a Postgres ENUM the way Articles' and
 * Places' own facet fields are. A single review row can propose into any
 * of four different term vocabularies depending on `facetKey`, and a
 * Postgres column can only ever back one ENUM — there is no single ENUM
 * that is simultaneously "every seeded type" and "every seeded subtype".
 * Enforcement instead happens in application code (`validateAgainstVocabulary`
 * below), checked against the SAME in-memory `vocabulary` map already
 * loaded once at boot for Articles/Places (`src/lib/vocabulary.ts`). This
 * is a real trade-off, stated plainly: a typo'd value is caught by this
 * field's `validate`, not by the database — but it also means the F20/F49
 * "new term needs a migration AND a restart of every cms-<city>" cost
 * does not apply to THIS collection's own schema at all (nothing here is
 * ENUM-backed) — only to whichever downstream Articles/Places field
 * `finalValue` eventually gets written onto still needs that restart to
 * accept a brand-new term. What the queue needs on restart: exactly what
 * Articles/Places already need (§20-ish new terms land in
 * `now_platform.engine.terms`, then every `cms-<city>` restarts to reload
 * `vocabulary` at boot) — nothing additional.
 */
export function buildClassificationReviewsCollection(vocabulary: VocabularyMap): CollectionConfig {
  const facetKeyOptions = CLASSIFICATION_FACETS.filter((key) => key in vocabulary)

  const validateAgainstVocabulary = (value: unknown, { siblingData }: { siblingData?: Record<string, unknown> }) => {
    if (!value) return true // empty is fine here — required-ness is enforced per review state, not per field
    const facetKey = siblingData?.facetKey as string | undefined
    if (!facetKey) return 'Set facetKey before a value can be validated against its vocabulary.'
    if (facetKey === 'type' && value === 'unknown') return true // F49 sentinel — always valid for "type"
    const validSlugs = new Set(optionsFor(vocabulary, facetKey).map((t) => t.value))
    if (validSlugs.size === 0) {
      // Vocabulary unreachable at boot (src/lib/vocabulary.ts logs this
      // loudly already) — degrade like every other facet field does rather
      // than block all review work until a restart.
      return true
    }
    return validSlugs.has(String(value))
      ? true
      : `"${value}" is not a seeded "${facetKey}" term. If the taxonomy just gained new terms, ` +
          `this CMS needs restarting (F20) to see them.`
  }

  const throughputEndpoint: Endpoint = {
    path: '/throughput',
    method: 'get',
    handler: async (req) => {
      const hoursParam = Number(req.query?.hours)
      const windowHours = Number.isFinite(hoursParam) && hoursParam > 0 ? hoursParam : 24
      const since = new Date(Date.now() - windowHours * 60 * 60 * 1000).toISOString()

      const reviewed = await req.payload.find({
        collection: 'classification-reviews',
        where: {
          and: [
            { reviewState: { not_equals: 'pending' } },
            { reviewedAt: { greater_than_equal: since } },
          ],
        },
        limit: 0,
        depth: 0,
      })

      const byReviewerCount = new Map<string, number>()
      for (const doc of reviewed.docs) {
        const reviewer = doc.reviewedBy ? String(doc.reviewedBy) : 'unknown'
        byReviewerCount.set(reviewer, (byReviewerCount.get(reviewer) ?? 0) + 1)
      }

      return Response.json({
        windowHours,
        reviewedCount: reviewed.totalDocs,
        itemsPerHour: Math.round((reviewed.totalDocs / windowHours) * 100) / 100,
        byReviewer: Array.from(byReviewerCount, ([reviewedBy, count]) => ({ reviewedBy, count })),
      })
    },
  }

  return {
    slug: 'classification-reviews',
    labels: { singular: 'Classification review', plural: 'Classification review queue' },
    admin: {
      useAsTitle: 'facetKey',
      defaultColumns: [
        'entityType',
        'facetKey',
        'legacyCategory',
        'proposedValue',
        'confidence',
        'confidenceBand',
        'reviewState',
        'siteSlug',
      ],
      description:
        'E2.1 low-confidence classifications, sorted shakiest-first. Accept, correct, or flag ' +
        'unclassifiable — corrections are training signal and are never overwritten by a re-run.',
    },
    // Sorted confidence ascending by default, in both the admin list view
    // and the Local API — "the shakiest first, so review time goes where
    // it is worth most" (this ticket's deliverable #1). Payload's `Sort`
    // type ascends on a bare field name, descends on a `-`-prefixed one.
    defaultSort: 'confidence',
    access: {
      read: () => true,
      create: isAuthorOrAbove,
      update: isAuthorOrAbove,
      delete: isEditorOrAbove,
    },
    hooks: {
      beforeChange: [deriveEntityType, autoPopulateOnDecision],
      afterChange: [makeApplyClassificationDecision(vocabulary)],
    },
    endpoints: [throughputEndpoint],
    fields: [
      {
        name: 'entity',
        label: 'Article or place',
        type: 'relationship',
        relationTo: ['articles', 'places'],
        required: true,
        admin: { description: 'Evidence #1 — the entity under review. Payload renders its title inline.' },
      },
      {
        name: 'entityType',
        type: 'select',
        options: ['article', 'place'],
        admin: { readOnly: true, description: 'Derived from `entity` — see deriveEntityType hook.' },
      },
      {
        name: 'legacyCategory',
        label: 'Legacy WP category',
        type: 'text',
        admin: {
          description:
            'Evidence #2 — the legacy WordPress category this entity carried (E1 extraction), ' +
            'captured as a snapshot at enqueue time. Not stored on the article/place itself — ' +
            'see this file\'s header comment for why.',
        },
      },
      {
        name: 'facetKey',
        label: 'Facet',
        type: 'select',
        required: true,
        options: [...facetKeyOptions],
        admin: {
          description:
            facetKeyOptions.length === 0
              ? 'No classification facets loaded — see PLATFORM_DATABASE_URI. Restart once reachable.'
              : 'Which of the four §6 classification facets this proposal is for.',
        },
      },
      {
        name: 'termId',
        label: 'Proposed term ID (platform DB)',
        type: 'text',
        admin: {
          description:
            'now_platform.engine.terms.id for proposedValue — carried through to the write-back ' +
            'event so engine-worker can upsert engine.entity_terms without a second lookup.',
        },
      },
      {
        name: 'proposedValue',
        label: 'Proposed value',
        type: 'text',
        required: true,
        validate: validateAgainstVocabulary,
        admin: { description: 'Evidence #3 — what the classifier proposed. Read-only in spirit; editors change `finalValue`, not this.' },
      },
      {
        name: 'confidence',
        type: 'number',
        required: true,
        min: 0,
        max: 1,
        admin: { description: 'Evidence #4. Queue is sorted ascending on this field — the shakiest first.' },
      },
      {
        name: 'confidenceBand',
        type: 'select',
        options: ['low', 'medium', 'high'],
        admin: {
          readOnly: true,
          description: 'Auto-computed from confidence (<0.5 low, <0.85 medium — the §17 auto-apply gate — else high). Filterable.',
        },
        hooks: {
          beforeChange: [
            ({ siblingData }) => {
              const c = Number(siblingData?.confidence)
              if (!Number.isFinite(c)) return undefined
              return c < 0.5 ? 'low' : c < 0.85 ? 'medium' : 'high'
            },
          ],
        },
      },
      {
        name: 'reasoning',
        type: 'textarea',
        required: true,
        admin: { description: "Evidence #5 — why the classifier chose it. Has no home in engine.entity_terms today; this field is its first one." },
      },
      {
        name: 'source',
        type: 'select',
        defaultValue: 'ai',
        options: ['ai', 'editor', 'inferred'],
        admin: { description: 'Mirrors engine.entity_terms.source exactly (same three values, same CHECK constraint intent).' },
      },
      { name: 'weight', type: 'number', defaultValue: 1, admin: { description: 'Mirrors engine.entity_terms.weight.' } },
      {
        name: 'reviewState',
        type: 'select',
        required: true,
        defaultValue: 'pending',
        options: ['pending', 'accepted', 'corrected', 'unclassifiable'],
        admin: {
          description:
            'One-click accept: set to "accepted" and save — finalValue auto-fills. Correct: set to ' +
            '"corrected" and type finalValue. Unclassifiable is a first-class outcome, not a forced ' +
            'wrong type (resolves to the F49 "unknown" sentinel for the type facet).',
        },
      },
      {
        name: 'finalValue',
        label: 'Final value',
        type: 'text',
        validate: validateAgainstVocabulary,
        admin: {
          description:
            'What actually gets written back onto the entity + announced to engine.entity_terms. ' +
            'Auto-copied from proposedValue on accept; typed by the editor on correct; the F49 ' +
            '"unknown" term for unclassifiable type reviews; left blank otherwise.',
        },
      },
      {
        name: 'reviewedBy',
        type: 'relationship',
        relationTo: 'users',
        admin: { readOnly: true, description: 'Auto-set from the acting user on decision.' },
      },
      {
        name: 'reviewedAt',
        type: 'date',
        admin: { readOnly: true, date: { pickerAppearance: 'dayAndTime' }, description: 'Auto-set on decision — the input to the throughput endpoint.' },
      },
      {
        name: 'siteSlug',
        label: 'City',
        type: 'text',
        defaultValue: () => process.env.SITE_SLUG ?? 'unknown',
        admin: {
          readOnly: true,
          description:
            'Cosmetic label + filter column (ARCHITECTURE.md §3.5 — SITE_SLUG is never branching ' +
            'logic). Every row in one cms-<city> instance shares this value today because content ' +
            'is DB-per-city; it becomes a genuine cross-city filter only if a future console merges ' +
            'multiple cities\' queues into one view (E4.4-shaped, not built here).',
        },
      },
    ],
  }
}
