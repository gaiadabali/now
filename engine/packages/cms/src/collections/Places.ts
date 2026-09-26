import type { CollectionConfig } from 'payload'

import { isAuthorOrAbove, isEditorOrAbove, isLoggedIn } from '../access'
import { vocabularySelectField } from '../fields/vocabularySelect'
import type { VocabularyMap } from '../lib/vocabulary'
import { GROUPS } from './groups'

/**
 * `places` — ARCHITECTURE.md §5 / §1 principle 1 ("places are first-class
 * entities, not article metadata"). This is a primary, high-frequency
 * editing surface, not an afterthought: geo, hours, price band and
 * amenities all need to be comfortably editable by non-technical editors.
 *
 * geo — ARCHITECTURE.md types this column `geography(Point,4326)` for
 * PostGIS `ST_DWithin` radius queries (§7 Row 2, §15). Payload's own
 * `point` field type maps to Postgres's native `point` type, not PostGIS
 * `geography` — using it as-is would silently hand engine-api a column it
 * cannot run `ST_DWithin` against. Rather than fight that with an
 * Alembic migration touching `public` (forbidden — Alembic never touches
 * `public`, full stop) we expose plain `lat`/`lng` number fields here for
 * editors, and a **Payload-owned** custom migration
 * (`src/migrations/002_places_geography.ts`) adds a real
 * `geography(Point,4326)` column plus a trigger that keeps it in sync from
 * lat/lng on every insert/update. Payload still owns every byte of DDL on
 * `public`; the trigger lives in the same schema Payload already owns and
 * runs entirely inside Postgres — no Alembic involvement. See that
 * migration file for the full rationale and the README's "genuine per-site
 * differences" section is unrelated to this — this is a Payload/PostGIS
 * field-type gap, not a site difference.
 */
export function buildPlacesCollection(vocabulary: VocabularyMap): CollectionConfig {
  return {
    slug: 'places',
    admin: {
      group: GROUPS.places,
      useAsTitle: 'name',
      defaultColumns: ['name', 'type', 'subtype', 'priceBand', 'status'],
      description: 'Venues, hotels, restaurants and other places. Curated constantly — keep edits fast.',
    },
    access: {
      read: () => true,
      create: isAuthorOrAbove,
      update: isAuthorOrAbove,
      delete: isEditorOrAbove,
    },
    // NOT `versions.drafts` — Payload's internal drafts column is named
    // `_status` and its generated Postgres enum type collided with the
    // enum generated for our own `status` field below (both sanitized to
    // the same Postgres identifier), producing an invalid migration where
    // `status` defaulted to 'active' against an enum containing only
    // 'draft'/'published'. Caught by actually running `payload
    // migrate:create` and reading the SQL rather than assuming it was
    // fine — see README.md "Payload quirk" note. Places also don't have
    // an editorial draft/publish concept in ARCHITECTURE.md (§5) the way
    // articles do — `status` here is a place lifecycle (active / closed /
    // pending_review), not an editorial workflow state — so plain version
    // history (no drafts) is the correct fit, not just a workaround.
    versions: { maxPerDoc: 20 },
    fields: [
      { name: 'name', type: 'text', required: true },
      { name: 'slug', type: 'text', required: true, unique: true, index: true },
      // Cross-database reference: orgs live in now_platform.engine.orgs, not
      // this database, so this cannot be a Payload `relationship` field —
      // Payload relationships only target collections in the same instance.
      // Stored as the org's platform-DB uuid; resolved by engine-api / the
      // console, which already read both databases.
      {
        name: 'orgId',
        label: 'Org ID (platform DB)',
        type: 'text',
        admin: { description: 'UUID of the owning org in now_platform.engine.orgs, if any.' },
      },
      {
        type: 'row',
        fields: [
          {
            name: 'lat',
            type: 'number',
            min: -90,
            max: 90,
            admin: { description: 'Decimal degrees. Leave both blank until geocoded (E2.5).' },
          },
          { name: 'lng', type: 'number', min: -180, max: 180 },
        ],
      },
      { name: 'address', type: 'text' },
      vocabularySelectField(vocabulary, {
        name: 'areaTerm',
        label: 'Area',
        facetKey: 'location',
        required: false,
        admin: { description: 'Fallback for Row 2 ranking when precise geo is missing (§7/§8.F).' },
      }),
      vocabularySelectField(vocabulary, { name: 'type', label: 'Type', facetKey: 'type', required: true }),
      vocabularySelectField(vocabulary, { name: 'subtype', label: 'Subtype', facetKey: 'subtype', required: true }),
      vocabularySelectField(vocabulary, {
        name: 'priceBand',
        label: 'Price band',
        facetKey: 'price_band',
        required: false,
      }),
      vocabularySelectField(vocabulary, {
        name: 'cuisine',
        label: 'Cuisine',
        facetKey: 'cuisine',
        hasMany: true,
      }),
      vocabularySelectField(vocabulary, {
        name: 'amenities',
        label: 'Amenities',
        facetKey: 'amenities',
        hasMany: true,
      }),
      vocabularySelectField(vocabulary, { name: 'vibe', label: 'Vibe', facetKey: 'vibe', hasMany: true }),
      {
        name: 'hours',
        label: 'Opening hours',
        type: 'array',
        admin: { description: 'One row per weekday. Leave a day out if closed.' },
        fields: [
          {
            type: 'row',
            fields: [
              {
                name: 'day',
                type: 'select',
                required: true,
                options: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'],
              },
              { name: 'opens', type: 'text', admin: { description: 'HH:MM, 24h' } },
              { name: 'closes', type: 'text', admin: { description: 'HH:MM, 24h' } },
            ],
          },
        ],
      },
      { name: 'avgDwellMin', label: 'Average dwell (minutes)', type: 'number', min: 0 },
      { name: 'bookingUrl', type: 'text' },
      { name: 'googlePlaceId', type: 'text', admin: { description: 'ARCHITECTURE.md §15 — store, never re-geocode.' } },
      {
        name: 'status',
        type: 'select',
        required: true,
        defaultValue: 'active',
        // 'junk' — ITINERARY-AND-READER-PRODUCTS-PLAN.md §9.2. A fourth
        // outcome, not a flag on 'closed': a junk row is a fragment the
        // extractor produced ("at Sunset Beach", a possessive, an award
        // title), never a real venue, never rendered and never a
        // candidate anywhere, but its `place_mentions` are kept as
        // evidence of what the extractor did. See migration
        // `20260926_090000_places_junk_status_enum_value.ts` for why the
        // enum label is added in its own migration, separate from the one
        // that adds these fields.
        options: ['active', 'closed', 'pending_review', 'junk'],
      },
      { name: 'verifiedAt', type: 'date' },
      // --- §9.2 provenance, geocoding and curation fields -----------------
      // Payload selects every declared column (README.md, this file's own
      // top comment), so this block and
      // `20260926_090100_places_provenance_and_curation_fields.ts` must ship
      // together — landing one without the other is a 500 on every place
      // read, not a missing feature.
      {
        name: 'source',
        type: 'select',
        required: true,
        admin: { description: 'Who created this row. Read-only in practice; set by the pipeline, not an editor.' },
        options: ['extracted', 'legacy_venue', 'editor', 'partner'],
      },
      {
        name: 'mergedInto',
        label: 'Merged into',
        type: 'relationship',
        relationTo: 'places',
        admin: {
          description:
            'Set when this row is a duplicate: points at the surviving place. A merged row is hidden ' +
            'everywhere (place page, candidates, rails) regardless of `status`.',
        },
      },
      {
        name: 'qualityScore',
        label: 'Quality score',
        type: 'number',
        admin: { readOnly: true, description: 'Computed nightly from evidence, completeness and freshness. Not editable.' },
      },
      {
        name: 'businessStatus',
        label: 'Business status',
        type: 'select',
        options: ['operational', 'temporarily_closed', 'permanently_closed', 'unknown'],
        admin: {
          description:
            'From the open gazetteers (FSQ/Overture) or an editor’s own confirmation — ' +
            'ARCHITECTURE.md/§9.4: never written from Google’s live business-status field.',
        },
      },
      {
        name: 'externalTypes',
        label: 'External types',
        type: 'json',
        admin: { description: 'The category list from the open gazetteers (FSQ/Overture) — typing evidence, not the type of record.' },
      },
      {
        name: 'geoSource',
        label: 'Geo source',
        type: 'select',
        options: ['fsq', 'overture', 'osm', 'mappress', 'editor', 'partner'],
        admin: {
          description:
            'The licence of THIS row’s coordinates — §9.4: OSM is ODbL (attribution required), ' +
            'FSQ/Overture carry their own notices. Set by the resolver, never blank on a geocoded row.',
        },
      },
      { name: 'geoConfidence', label: 'Geo confidence', type: 'number' },
      {
        name: 'regionOk',
        label: 'In region',
        type: 'checkbox',
        defaultValue: false,
        admin: {
          description:
            'Computed: do this row’s coordinates fall inside the site’s own region? false = ' +
            'mention-only — a venue from a neighbouring city, kept because a story here mentions ' +
            'it, but never a candidate for this site.',
        },
      },
      {
        name: 'hoursSource',
        label: 'Hours source',
        type: 'select',
        options: ['editor', 'partner'],
        admin: { description: 'Never `google` — §9.4 forbids storing Google’s hours. Editor-entered or partner-maintained only.' },
      },
      { name: 'hoursCheckedAt', label: 'Hours checked', type: 'date' },
      {
        name: 'legacyWpId',
        label: 'Legacy WP ID',
        type: 'number',
        index: true,
        unique: true,
        admin: {
          description:
            'venues.jsonl `wp_id` (WordPress tribe_venue post id), where this place originated ' +
            'from a legacy WP venue import — same idempotency-key convention as Events/Articles ' +
            '(F99 final report). NULL for the majority of places, which came from E2.3 text ' +
            'extraction and have no single source WP entity.',
        },
      },
    ],
  }
}
