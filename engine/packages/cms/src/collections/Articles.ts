import type { CollectionConfig } from 'payload'

import { isAuthorOrAbove, isEditorOrAbove } from '../access'
import { bodyBlocksField } from '../fields/bodyBlocks'
import { slugField } from '../fields/slug'
import { vocabularySelectField } from '../fields/vocabularySelect'
import { enforcePublishRole } from '../hooks/enforcePublishRole'
import { publishArticleEvent } from '../hooks/publishArticleEvent'
import type { VocabularyMap } from '../lib/vocabulary'
import { GROUPS } from './groups'

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
      group: GROUPS.editorial,
      useAsTitle: 'title',
      defaultColumns: ['title', 'primaryType', 'format', 'publishedAt', '_status'],
      description: 'Editorial articles, guides and news.',
      /**
       * See it as a reader will, before anyone else can (S4).
       *
       * Both of these point at `/preview`, which checks for an editorial role,
       * turns on Next's draft mode for that browser and redirects to the story
       * at its real address. `preview` puts a button in the document header
       * that opens it in a tab; `livePreview` adds the side-by-side view with
       * the page in an iframe.
       *
       * A relative URL on purpose. The admin and the reader site are the same
       * app on the same origin, so there is nothing to point an absolute URL
       * at that would not be a hostname literal — and §3.5 forbids those, with
       * `npm run lint:site-literals` to enforce it.
       *
       * The iframe refreshes when the document is saved, and autosave runs
       * every 1.5s, so in practice it tracks typing within a second or two.
       * True keystroke-level updating needs `@payloadcms/live-preview-react`
       * in the reader app to listen for Payload's postMessage; that is one
       * npm dependency and a `RefreshRouteOnSave` component, deliberately not
       * bundled into this change.
       *
       * Every article has an address to preview at only because of S1.1.
       * Before that an unpublished article had no URL at all, which is why
       * this could not have been built first.
       */
      preview: (doc) => (doc?.id ? `/preview?collection=articles&id=${doc.id}` : null),
      livePreview: {
        url: ({ data }) => (data?.id ? `/preview?collection=articles&id=${data.id}` : '/'),
        // The reader site has exactly two breakpoints (62rem and 36rem), so
        // these are the widths either side of each one rather than a generic
        // phone/tablet/desktop set that would test nothing in particular.
        breakpoints: [
          { name: 'phone', label: 'Phone', width: 390, height: 844 },
          { name: 'tablet', label: 'Tablet', width: 820, height: 1180 },
          { name: 'desktop', label: 'Desktop', width: 1440, height: 900 },
        ],
      },
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
    /**
     * S3.3 — the writing surface is the page, and everything else is beside it.
     *
     * This was one flat column of twelve fields, in this order: kind, title,
     * dek, body, hero, author, primary type, format, published at, **legacy WP
     * ID, legacy permalink**, series key. So a writer scrolled past "The old
     * WordPress post number. Nothing to change here." and a field whose
     * description shouts DO NOT EDIT, on the way to the bottom of their own
     * article. Nothing was hidden and nothing was prioritised.
     *
     * Three moves, no field removed and no data path changed:
     *
     *   SIDEBAR   the four decisions that are not the writing — when it runs,
     *             what it is about, what shape it is, what sort of thing it
     *             is. They sit next to Payload's own status and publish
     *             controls, which is where a writer already looks to answer
     *             "is this ready", and they stay visible while the body is
     *             scrolled.
     *   STORY     the tab that opens by default: headline, address, dek, the
     *             picture, the byline, and the body. Everything a writer
     *             touches and nothing else.
     *   OLD SITE  the three import fields, behind a tab, with the warning kept
     *             verbatim because it is still true.
     *
     * The tabs are UNNAMED on purpose. A named tab nests its children's data
     * under that name, which would move every one of these columns and need a
     * migration; an unnamed tab is presentation only, so `title` is still
     * `title` and the slug hook, the publish hooks and the version table are
     * all untouched.
     *
     * Primary type and format are required and are in the sidebar rather than
     * behind a tab deliberately: a required field on a tab a writer never
     * opens is a save that fails for a reason they cannot see.
     */
    fields: [
      /* ---------------------------------------------------------- sidebar */
      {
        name: 'publishedAt',
        label: 'Published at',
        type: 'date',
        admin: {
          position: 'sidebar',
          date: { pickerAppearance: 'dayAndTime' },
          description:
            'The dateline. Set it in the future and use Publish changes → schedule to have it ' +
            'go live then.',
        },
      },
      vocabularySelectField(vocabulary, {
        name: 'primaryType',
        label: 'What it is about',
        facetKey: 'type',
        required: true,
        admin: {
          position: 'sidebar',
          description:
            'Eat, drink, stay, do, shop, event, wellness or editorial. The most consequential ' +
            'field on this page: it is what keeps a restaurant’s advert off a rival ' +
            'restaurant’s article, which is something partners are paying for (§8.A competitor ' +
            'exclusion, and it never relaxes at any tier).',
        },
      }),
      vocabularySelectField(vocabulary, {
        name: 'format',
        label: 'What kind of writing',
        facetKey: 'format',
        required: true,
        admin: {
          position: 'sidebar',
          description:
            'News, feature, review, guide, offer, opinion, listing, people. A different ' +
            'question from what it is about — a review of a restaurant is eat + review, a ' +
            'restaurant’s promotion is eat + offer. This decides how fast the piece stops ' +
            'being recommended: a review stays useful for years, an offer is stale in a month.',
        },
      }),
      {
        name: 'kind',
        type: 'select',
        required: true,
        defaultValue: 'article',
        options: ['article', 'guide', 'itinerary_narrative'],
        admin: {
          position: 'sidebar',
          description: 'Leave this as "article" unless you mean otherwise.',
        },
      },
      /**
       * Edition 2, WS3 — "the writing screen, for non-developers". A `ui`
       * field stores nothing (no column, no migration): it is purely a slot
       * for `PublishChecklist.tsx`, which reads the sidebar/tab fields above
       * through Payload's own form state and answers one question a writer
       * actually asks while working — "is this ready, and what will it look
       * like out there" — instead of the twelve stored columns this sidebar
       * used to be. See that component's header for what it does and does
       * not check, and why two of its checks need a fetch.
       */
      {
        name: 'publishChecklist',
        type: 'ui',
        admin: {
          position: 'sidebar',
          components: { Field: '/fields/PublishChecklist#PublishChecklist' },
        },
      },

      /* ------------------------------------------------------ main column */
      {
        type: 'tabs',
        tabs: [
          {
            label: 'Story',
            admin: {
              description: 'The article as a reader meets it.',
            },
            fields: [
              {
                name: 'title',
                type: 'text',
                required: true,
                admin: {
                  description: 'The headline, as a reader sees it.',
                  // "The one idea worth protecting" (docs/DESIGN-SYSTEM.md
                  // §5): set in Cormorant 300 at `--t-display`, the same face
                  // and size a reader meets it in, on a `--hair` rule with no
                  // box — see `.now-field--headline` in styles/admin.css.
                  // A `className`, not a custom `Field` component: Payload
                  // merges `admin.className` onto the field's own wrapper for
                  // every field type (confirmed against
                  // `@payloadcms/ui/dist/fields/Text/Input.js`), so this reads
                  // the stock text field and its autosave/validation exactly
                  // as before — no new entry in the generated import map, no
                  // F143 exposure, for a change that is purely visual.
                  className: 'now-field--headline',
                },
              },
              // Directly under the headline, because that is where it comes
              // from and where every other editor puts it. `legacyPermalink`
              // on the next tab is the OLD site's address and stays
              // untouchable; this is the one the story is served at from now
              // on. Both resolve — see `getBySlug` in the reader app — so an
              // imported article keeps its inbound links whatever happens
              // here.
              slugField,
              {
                name: 'dek',
                label: 'Standfirst',
                type: 'textarea',
                admin: {
                  description:
                    'The sentence under the headline that makes someone read on. Around 1,800 ' +
                    'imported articles have none — worth writing one while you are in here.',
                  // Italic Cormorant `--t-lede`, in a bordered field (§5) —
                  // the standfirst voice §1 reserves italics for.
                  className: 'now-field--standfirst',
                },
              },
              {
                name: 'heroMedia',
                label: 'Main picture',
                type: 'upload',
                relationTo: 'media',
                admin: {
                  description:
                    'The picture at the top of the article and in listings. Uploading does not ' +
                    'work yet — Media has no storage behind it, so existing pictures stay and ' +
                    'new ones cannot be added (docs/DEPLOY.md §6).',
                },
              },
              {
                name: 'author',
                label: 'Byline',
                type: 'relationship',
                relationTo: 'authors',
                admin: { description: 'Who wrote it. Shown on the article and on their author page.' },
              },
              bodyBlocksField,
            ],
          },
          {
            label: 'Old site',
            admin: {
              description:
                'How this article was addressed on the WordPress site it came from. Nothing ' +
                'here needs changing, and one field must not be.',
            },
            fields: [
              {
                name: 'legacyPermalink',
                label: 'Address on the old site',
                type: 'text',
                index: true,
                admin: {
                  description:
                    'DO NOT EDIT — every redirect from the old site is matched on this exact ' +
                    'string (§9), so changing it breaks the links readers already have and ' +
                    'anything Google has indexed. To change where this story lives, edit the ' +
                    'web address on the Story tab: both keep working.',
                },
              },
              {
                name: 'legacyWpId',
                label: 'Old WordPress post number',
                type: 'number',
                index: true,
                unique: true,
                admin: { description: 'The number this article had on the old site. Nothing to change here.' },
              },
              {
                name: 'seriesKey',
                label: 'Series',
                type: 'text',
                index: true,
                admin: {
                  description:
                    'Groups annual repeats of the same piece together — "Best Beach Clubs 2024", ' +
                    '2025, 2026. Usually blank; give the whole run the same short word to link ' +
                    'them.',
                },
              },
            ],
          },
        ],
      },
    ],
  }
}
