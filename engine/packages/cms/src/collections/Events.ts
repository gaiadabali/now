import type { CollectionConfig } from 'payload'

import { isAuthorOrAbove, isEditorOrAbove } from '@/access'
import { bodyBlocksField } from '@/fields/bodyBlocks'

/**
 * `events` — ARCHITECTURE.md §5. Tied to a place; supports one-off and
 * recurring (`rrule`) occurrences. §6 notes 490 legacy `upcoming-events`
 * rows have no structured start/end date — those are a load-time gap
 * (E1.8/F26), not a reason to make `startsAt` optional here; that call
 * stands and is not touched by this change.
 *
 * **PROGRESS.md F28 — content columns added (this migration).** E1.8's
 * loader reported that all 837 source event rows carry a title, a rich
 * `content_html` write-up, an excerpt and a thumbnail, and none of it had
 * anywhere to go: the collection had only the five time/place/ticket
 * columns. Design options weighed (see this ticket's final report for the
 * full write-up):
 *
 *   1. Content columns directly on `events` (title/dek/bodyBlocks/heroMedia)
 *   2. `events.article_id` FK, content lives only in `articles`
 *   3. Both
 *
 * **Chosen: 3, both — but asymmetric, not "duplicate everything twice."**
 * Inspecting the real source extraction (`content/extracted/events.jsonl`)
 * shows these 837 rows are WordPress `tribe_events`/`upcoming-events` posts
 * — a distinct legacy post type from `articles.jsonl`. There is no existing
 * `articles` row for the vast majority of them; option 2 alone would strand
 * the write-up with nowhere to land. So content columns are the load-bearing
 * fix (below), sized identically to Articles' own title/dek/bodyBlocks/
 * heroMedia so §12's itinerary stops and §8's rails can render an event as a
 * card without a join. `article` (a relationship to `articles`) is added
 * *in addition*, but as an optional pointer only — for the case where an
 * editor later writes a full feature about a recurring festival and wants
 * to link the event stop to it. It is never a substitute for `bodyBlocks`,
 * and the loader must not synthesize it (no source field maps one to the
 * other) — see the final report's backfill note for exactly what does and
 * does not get populated.
 */
export const Events: CollectionConfig = {
  slug: 'events',
  admin: {
    useAsTitle: 'title',
    defaultColumns: ['title', 'place', 'startsAt', 'endsAt', '_status'],
  },
  access: {
    read: () => true,
    create: isAuthorOrAbove,
    update: isAuthorOrAbove,
    delete: isEditorOrAbove,
  },
  versions: { drafts: true },
  fields: [
    {
      name: 'title',
      type: 'text',
      required: true,
      defaultValue: 'Untitled event',
      admin: {
        description:
          'Required for §12 itinerary stops and §8 rails to render this event without joining ' +
          'to a place or article. Source: events.jsonl `title`. The default only applies to new, ' +
          'editor-created events — see the final report for how the 837 pre-existing rows are backfilled.',
      },
    },
    { name: 'dek', label: 'Dek (standfirst)', type: 'textarea', admin: { description: 'Source: events.jsonl `excerpt`.' } },
    bodyBlocksField,
    {
      name: 'heroMedia',
      label: 'Hero image',
      type: 'upload',
      relationTo: 'media',
      admin: { description: 'Source: events.jsonl `thumbnail_id`, resolved via the media wp_id map, same as Articles.heroMedia.' },
    },
    { name: 'place', type: 'relationship', relationTo: 'places', required: true },
    { name: 'startsAt', type: 'date', required: true, admin: { date: { pickerAppearance: 'dayAndTime' } } },
    { name: 'endsAt', type: 'date', admin: { date: { pickerAppearance: 'dayAndTime' } } },
    {
      name: 'rrule',
      label: 'Recurrence rule (RFC 5545)',
      type: 'text',
      admin: { description: 'e.g. FREQ=WEEKLY;BYDAY=FR — leave blank for a one-off event.' },
    },
    { name: 'ticketUrl', type: 'text' },
    {
      name: 'article',
      label: 'Related article (optional)',
      type: 'relationship',
      relationTo: 'articles',
      admin: {
        description:
          'Optional link to a fuller editorial feature about this event or its recurring series ' +
          "(e.g. an annual festival write-up). Not a substitute for this event's own title/dek/" +
          'bodyBlocks above — leave null unless a real companion article exists. The loader does ' +
          'not populate this field; no events.jsonl field maps to it.',
      },
    },
    {
      name: 'legacyWpId',
      label: 'Legacy WP ID',
      type: 'number',
      index: true,
      unique: true,
      admin: { description: 'events.jsonl `wp_id`. Enables idempotent upsert — see final report.' },
    },
  ],
}
