/**
 * Content access, backed by the city database via Payload's Local API.
 *
 * Was fixture-backed through the comp phase; `docs/ui-data-layer.md` is the
 * contract this now satisfies. Every signature is unchanged from that era,
 * which is the point — no page changed when the source did.
 *
 * The boundary from that document holds: articles come from the Local API
 * (same process, city DB), while ranked rails, search and facet counts come
 * from engine-api. This module never queries Postgres directly and never
 * writes.
 */

import { SECTION_TO_TYPES, payloadClient, toArticle } from '@/lib/payload'
import { slugify } from '@/lib/format'

export type Article = {
  id: number
  title: string
  slug: string
  date: string
  section: string
  categories: string[]
  tags: string[]
  image: string
  dek: string
  paras: string[]
  views: number
}

/**
 * Editorial sections, in masthead order.
 *
 * The values were legacy WordPress category *names* during the comp phase.
 * Those names are not a column — E1/E2 turned the archive's categories into
 * taxonomy terms — so sections are now derived from the §4 L1 `primaryType`
 * in `lib/payload.ts`. The keys, which are the public URLs, are unchanged.
 */
const SECTION_MAP: Record<string, string[]> = {
  dining: ['dining'],
  stay: ['stay'],
  culture: ['culture'],
  wellness: ['wellness'],
  'things-to-do': ['things-to-do'],
}

export function sectionOf(article: Article): string {
  for (const [slug, cats] of Object.entries(SECTION_MAP)) {
    if (cats.includes(article.section)) return slug
  }
  return slugify(article.section)
}

export function isSectionSlug(slug: string): boolean {
  return slug in SECTION_MAP
}

export function sectionLabel(slug: string): string {
  return slug
    .split('-')
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join(' ')
}

/** Published only, newest first. `_status` is Payload's draft/publish flag. */
const PUBLISHED = { _status: { equals: 'published' } } as const

export async function getLatest(limit = 20): Promise<Article[]> {
  const payload = await payloadClient()
  const { docs } = await payload.find({
    collection: 'articles',
    where: PUBLISHED,
    sort: '-publishedAt',
    limit,
    depth: 1, // resolves heroMedia to a document rather than an id
  })
  return docs.map(toArticle)
}

export async function getLead(): Promise<Article | undefined> {
  const [lead] = await getLatest(1)
  return lead
}

export async function getBySection(
  slug: string,
  limit = 12,
  format?: string,
): Promise<Article[]> {
  const types = SECTION_TO_TYPES[slug]
  if (!types) return []

  const payload = await payloadClient()
  const { docs } = await payload.find({
    collection: 'articles',
    where: {
      ...PUBLISHED,
      primaryType: { in: types },
      ...(format ? { format: { equals: format } } : {}),
    },
    sort: '-publishedAt',
    limit,
    depth: 1,
  })
  return docs.map(toArticle)
}

export type Facet = { label: string; value: string | null; count: number }

/** Human labels for the §4 `format` vocabulary. */
const FORMAT_LABELS: Record<string, string> = {
  news: 'News',
  feature: 'Features',
  review: 'Reviews',
  'city-guide': 'Guides',
  offer: 'Offers',
  event: 'Events',
  people: 'People',
  interview: 'Interviews',
  listicle: 'Lists',
}

/**
 * Real facet counts for a section index.
 *
 * Replaces the comp's hardcoded chips (`Ubud 34`, `$$ 41`), which were
 * invented design values wired to nothing — they neither counted nor
 * filtered, and on a live site they were simply false.
 *
 * Faceted on `format` rather than area or price because those are the
 * attributes articles actually carry. Area and price live on `places`, and a
 * section index lists articles; the comp borrowed a place filter for an
 * article page.
 *
 * §9's "count with every filter EXCEPT the facet being counted" is satisfied
 * trivially here: `format` is the only reader-facing filter on this page, so
 * each count is taken with it lifted. The moment a second filter is added,
 * this has to grow an exclusion or the counts start lying by a different
 * mechanism.
 */
export async function getSectionFacets(slug: string): Promise<Facet[]> {
  const types = SECTION_TO_TYPES[slug]
  if (!types) return []

  const payload = await payloadClient()
  const base = { ...PUBLISHED, primaryType: { in: types } }

  // `limit: 0` asks Postgres for the count without fetching rows.
  const total = await payload.count({ collection: 'articles', where: base })

  const counted = await Promise.all(
    Object.entries(FORMAT_LABELS).map(async ([value, label]) => ({
      label,
      value,
      count: (await payload.count({
        collection: 'articles',
        where: { ...base, format: { equals: value } },
      })).totalDocs,
    })),
  )

  return [
    { label: 'All', value: null, count: total.totalDocs },
    // A chip counting zero is noise, not information.
    ...counted.filter((f) => f.count > 0).sort((a, b) => b.count - a.count),
  ]
}

export async function getBySlug(slug: string): Promise<Article | undefined> {
  const payload = await payloadClient()
  // Matched on `legacyPermalink`, not a title-derived slug: those URLs are
  // the traffic (LIVE_RECON), and they must keep resolving after an edit.
  const { docs } = await payload.find({
    collection: 'articles',
    where: { ...PUBLISHED, legacyPermalink: { equals: `/${slug}/` } },
    limit: 1,
    depth: 1,
  })
  return docs[0] ? toArticle(docs[0]) : undefined
}

/**
 * Most read.
 *
 * Returns recency for now, NOT imported view counts. §6: WordPress's
 * `wpb_post_views_count` is bot-contaminated, so carrying it across would
 * put a number on the page that nobody can defend. The real implementation
 * recomputes from beacon interactions — which do not exist yet, because the
 * beacon has not been deployed (blocker B2). Recency is the honest stand-in;
 * inventing a ranking would not be.
 */
export async function getMostRead(limit = 5): Promise<Article[]> {
  return getLatest(limit)
}

/**
 * Related content.
 *
 * Same-section recency, not the engine's rails. `GET /v1/{site}/articles/{id}/rails`
 * is live and is the correct source, but §10's presentation-bias warning cuts
 * both ways: wiring the rails in means their impressions must be logged with
 * rail and position, and the beacon that does that is not deployed yet. A
 * ranked rail whose impressions go unrecorded trains nothing and teaches the
 * eventual model that whatever shipped first was right.
 *
 * So this stays a simple, honest fallback until the beacon lands, at which
 * point it becomes one fetch.
 */
export async function getRelated(article: Article, limit = 3): Promise<Article[]> {
  const section = sectionOf(article)
  const candidates = await getBySection(section, limit + 1)
  return candidates.filter((a) => a.id !== article.id).slice(0, limit)
}

/*
 * Comp-phase stand-ins for content the engine will supply. They live under
 * `src/fixtures/` so the site-literal guard treats them as sample data, not
 * as code that knows which city it serves.
 */
export { GUIDES, EVENTS, PLACE } from '@/fixtures/editorial'
