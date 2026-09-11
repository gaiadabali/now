import type { CollectionConfig } from 'payload'

import { isAuthorOrAbove, isEditorOrAbove } from '@/access'
import { bodyBlocksField } from '@/fields/bodyBlocks'
import { vocabularySelectField } from '@/fields/vocabularySelect'
import { enforcePublishRole } from '@/hooks/enforcePublishRole'
import { publishArticleEvent } from '@/hooks/publishArticleEvent'
import type { VocabularyMap } from '@/lib/vocabulary'

/**
 * `articles` — ARCHITECTURE.md §5.
 *
 * `status` in the architecture doc maps to Payload's own `_status` column
 * (draft/published), which `versions.drafts` below creates and manages —
 * a second, hand-rolled `status` field would fight Payload's native
 * versioning instead of using it. Scheduled publish uses Payload's built-in
 * `schedulePublish`, which reads `publishedAt` (below) as the publish-at
 * timestamp. This is the one deliberate naming deviation from §5's column
 * list; see this ticket's final report for the full note.
 */
export function buildArticlesCollection(vocabulary: VocabularyMap): CollectionConfig {
  return {
    slug: 'articles',
    admin: {
      useAsTitle: 'title',
      defaultColumns: ['title', 'primaryType', 'format', 'publishedAt', '_status'],
      description: 'Editorial articles, guides and news.',
    },
    access: {
      read: () => true,
      create: isAuthorOrAbove,
      update: isAuthorOrAbove,
      delete: isEditorOrAbove,
    },
    versions: {
      drafts: {
        autosave: { interval: 1500 },
        schedulePublish: true,
      },
      maxPerDoc: 50,
    },
    hooks: {
      beforeChange: [enforcePublishRole],
      afterChange: [publishArticleEvent],
    },
    fields: [
      {
        name: 'kind',
        type: 'select',
        required: true,
        defaultValue: 'article',
        options: ['article', 'guide', 'itinerary_narrative'],
        admin: { description: '"guide" powers /guides/{slug} (§9 URL structure).' },
      },
      { name: 'title', type: 'text', required: true },
      { name: 'dek', label: 'Dek (standfirst)', type: 'textarea' },
      bodyBlocksField,
      {
        name: 'heroMedia',
        label: 'Hero image',
        type: 'upload',
        relationTo: 'media',
      },
      {
        name: 'author',
        type: 'relationship',
        relationTo: 'authors',
      },
      vocabularySelectField(vocabulary, {
        name: 'primaryType',
        label: 'Primary type',
        facetKey: 'type',
        required: true,
        admin: { description: 'Drives competitor exclusion (§8.A) — never relaxes at any tier.' },
      }),
      vocabularySelectField(vocabulary, {
        name: 'format',
        label: 'Format',
        facetKey: 'format',
        required: true,
        admin: { description: 'Drives decay half-life (§4 Format → decay half-life table).' },
      }),
      {
        name: 'publishedAt',
        label: 'Published at',
        type: 'date',
        admin: { date: { pickerAppearance: 'dayAndTime' } },
      },
      { name: 'legacyWpId', label: 'Legacy WP ID', type: 'number', index: true, unique: true },
      {
        name: 'legacyPermalink',
        label: 'Legacy permalink',
        type: 'text',
        index: true,
        admin: { description: 'MUST match the WordPress permalink exactly (§9) — 301s depend on it.' },
      },
      {
        name: 'seriesKey',
        label: 'Series key',
        type: 'text',
        index: true,
        admin: { description: 'Clusters annual "[Updated]" listicles (§6 known issues, E2.6).' },
      },
    ],
  }
}
