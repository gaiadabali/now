import type { CollectionConfig } from 'payload'

import { isAuthorOrAbove, isEditorOrAbove } from '../access'
import { enforcePublishRole } from '../hooks/enforcePublishRole'
import { GROUPS } from './groups'

/**
 * `editions` — ITINERARY-AND-READER-PRODUCTS-PLAN.md §5.1-§5.2.
 *
 * "Editions are city content in Payload; commerce is platform data" (§5.1):
 * a magazine issue — its cover, issue label, on-sale date and contents list
 * — is editorial content exactly like an article, so it lives here, next to
 * Articles, in the same city database. Buying a copy is a person doing
 * something with money and an address, which is platform data like every
 * other reader/commerce table (§5.4's `engine.print_*`, migration 0014) —
 * an order line references `(site_id, edition_id)`, the same cross-database
 * pattern as everything else in this plan, never a same-database FK.
 *
 * `status` maps to Payload's own `_status` (draft/published) via
 * `versions.drafts`, same deliberate naming deviation `Articles.ts`'s own
 * docstring already documents for that collection — a second, hand-rolled
 * `status` field would fight Payload's native versioning rather than use
 * it. `enforcePublishRole` is reused unchanged: it reads `data._status`
 * generically and does not care which collection it is attached to.
 *
 * "This month's edition" (§5.2) — latest published edition with
 * `on_sale_at <= today` — is a query the reader app makes
 * (`WHERE _status = 'published' AND on_sale_at <= now() ORDER BY on_sale_at
 * DESC LIMIT 1`), not a flag this collection stores; storing "is this the
 * current one" as a boolean would need updating every prior edition's row
 * the moment a new one goes on sale, which is exactly the kind of derived
 * state a query should compute instead of a write path maintaining it.
 *
 * No versions/drafts complexity beyond the standard; `maxPerDoc` matches
 * `Places.ts`'s value (20) rather than `Articles.ts`'s (50) — an edition is
 * revised occasionally before publishing (cover swapped, contents
 * finalised), not iterated on at article-writing cadence.
 */
export const Editions: CollectionConfig = {
  slug: 'editions',
  admin: {
    group: GROUPS.editorial,
    useAsTitle: 'title',
    defaultColumns: ['title', 'issueDate', 'onSaleAt', '_status', 'soldOut'],
    description: 'The print edition, per city: cover, issue date, on-sale date, contents.',
  },
  access: {
    read: () => true,
    create: isAuthorOrAbove,
    update: isAuthorOrAbove,
    delete: isEditorOrAbove,
  },
  versions: {
    drafts: true,
    maxPerDoc: 20,
  },
  hooks: {
    beforeChange: [enforcePublishRole],
  },
  fields: [
    // Deliberately NOT `required: true` on title/issueDate/cover, matching
    // `Articles.ts`'s own choice for `title`: this collection autosaves
    // drafts (`versions.drafts` below), and Payload mirrors a `required`
    // field's `NOT NULL` onto the *version* table too (confirmed against
    // `Places.ts`'s required fields and `_places_v` — `version_name`/
    // `version_type` etc. are `NOT NULL` there) — which would make
    // autosaving a brand-new, still-empty draft fail at the database layer.
    // "Must be set before publish" is an editorial expectation this
    // collection relies on `enforcePublishRole`'s reviewer to check, not a
    // constraint enforced at every keystroke of a draft.
    { name: 'title', type: 'text', admin: { description: 'e.g. "October 2026".' } },
    { name: 'issueLabel', label: 'Issue label', type: 'text', admin: { description: 'e.g. "No. 214". Optional.' } },
    {
      name: 'issueDate',
      label: 'Issue (cover) date',
      type: 'date',
      unique: true,
      admin: { description: 'The cover date. One edition per issue date, per city — the cadence is data, not code.' },
    },
    { name: 'cover', type: 'upload', relationTo: 'media' },
    {
      name: 'onSaleAt',
      label: 'On sale from',
      type: 'date',
      admin: {
        description:
          '"This month’s edition" = the latest published edition with an on-sale date on or before today.',
      },
    },
    { name: 'soldOut', label: 'Sold out', type: 'checkbox', defaultValue: false },
    {
      name: 'priceIdr',
      label: 'Single-copy price (IDR)',
      type: 'number',
      min: 0,
      admin: { description: 'Leave blank if this issue is not sold individually (subscription-only).' },
    },
    {
      name: 'contents',
      type: 'array',
      admin: { description: 'The issue’s contents list, in reading order.' },
      fields: [
        // Not `required: true` — same autosave-vs-version-table-NOT-NULL
        // reasoning as the top-level fields above, and doubly so here: a
        // brand new array row an editor just clicked "add" on is blank for
        // a moment before they type anything, and autosave runs on that
        // moment too.
        { name: 'heading', type: 'text' },
        {
          name: 'article',
          type: 'relationship',
          relationTo: 'articles',
          admin: { description: 'Optional — set once the piece is online, to link the contents entry to it.' },
        },
        { name: 'blurb', type: 'textarea' },
      ],
    },
    {
      name: 'replicaPdf',
      label: 'Replica PDF',
      type: 'upload',
      relationTo: 'media',
      admin: {
        description:
          'Optional. Served only to buyers/subscribers — that gate is a later phase; this field only stores the file.',
      },
    },
    { name: 'notes', type: 'textarea', admin: { description: 'Internal notes. Never shown to a reader.' } },
  ],
}
