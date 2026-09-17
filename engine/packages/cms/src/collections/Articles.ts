import type { CollectionConfig } from 'payload'

import { isAuthorOrAbove, isEditorOrAbove } from '../access'
import { bodyBlocksField } from '../fields/bodyBlocks'
import { vocabularySelectField } from '../fields/vocabularySelect'
import { enforcePublishRole } from '../hooks/enforcePublishRole'
import { publishArticleEvent } from '../hooks/publishArticleEvent'
import type { VocabularyMap } from '../lib/vocabulary'

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
        admin: {
          description:
            'What sort of thing this is. Leave it as "article" unless you mean otherwise — ' +
            '"guide" changes the web address to /guides/… (§9 URL structure).',
        },
      },
      {
        name: 'title',
        type: 'text',
        required: true,
        admin: { description: 'The headline, as a reader sees it.' },
      },
      {
        name: 'dek',
        label: 'Dek (standfirst)',
        type: 'textarea',
        admin: {
          description:
            'The sentence under the headline that makes someone read on. Around 1,800 ' +
            'imported articles have none — worth writing one while you are in here.',
        },
      },
      bodyBlocksField,
      {
        name: 'heroMedia',
        label: 'Hero image',
        type: 'upload',
        relationTo: 'media',
        admin: {
          description:
            'The picture at the top of the article and in listings. Uploading does not work ' +
            'yet — `Media` has no storage behind it, so existing images stay and new ones ' +
            'cannot be added (docs/DEPLOY.md section 6).',
        },
      },
      {
        name: 'author',
        type: 'relationship',
        relationTo: 'authors',
        admin: { description: 'Who wrote it. Shown on the article and on their author page.' },
      },
      vocabularySelectField(vocabulary, {
        name: 'primaryType',
        label: 'Primary type',
        facetKey: 'type',
        required: true,
        admin: {
          description:
            'What the piece is ABOUT, as a thing a reader wants: eat, drink, stay, do, shop, ' +
            'event, wellness, or editorial. The most consequential field on this page — it is ' +
            'what keeps a restaurant’s advert off a rival restaurant’s article, which is a ' +
            'paid guarantee (§8.A competitor exclusion, and it never relaxes at any tier).',
        },
      }),
      vocabularySelectField(vocabulary, {
        name: 'format',
        label: 'Format',
        facetKey: 'format',
        required: true,
        admin: {
          description:
            'What SHAPE of writing it is: news, feature, review, guide, offer, opinion, ' +
            'listing, people. A different question from Primary type — "a review of a ' +
            'restaurant" is eat + review, "a restaurant’s promotion" is eat + offer. This ' +
            'decides how fast the piece ages out of recommendations (§4 decay half-life): a ' +
            'review stays useful for years, an offer is stale in a month.',
        },
      }),
      {
        name: 'publishedAt',
        label: 'Published at',
        type: 'date',
        admin: {
          date: { pickerAppearance: 'dayAndTime' },
          description:
            'The dateline. Set it in the future and use Publish changes → schedule to have it ' +
            'go live then.',
        },
      },
      {
        name: 'legacyWpId',
        label: 'Legacy WP ID',
        type: 'number',
        index: true,
        unique: true,
        admin: { description: 'The old WordPress post number. Nothing to change here.' },
      },
      {
        name: 'legacyPermalink',
        label: 'Legacy permalink',
        type: 'text',
        index: true,
        admin: {
          description:
            'The article’s address on the old WordPress site. DO NOT EDIT — every redirect ' +
            'from the old site is matched on this exact string (§9), so changing it breaks the ' +
            'links readers already have and anything Google has indexed.',
        },
      },
      {
        name: 'seriesKey',
        label: 'Series key',
        type: 'text',
        index: true,
        admin: {
          description:
            'Groups annual repeats of the same piece together — "Best Beach Clubs 2024", ' +
            '2025, 2026. Usually blank; give the whole run the same short word to link them ' +
            '(§6 known issues, E2.6).',
        },
      },
    ],
  }
}
