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

import {
  SECTION_TO_TYPES,
  articleIdsForTermSlugs,
  heroMediaId,
  legacyMediaUrls,
  payloadClient,
  sectionFormatCounts,
  toArticle,
} from '@/lib/payload'
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
  wellness: ['wellness'],
  'things-to-do': ['things-to-do'],
  events: ['events'],
  guides: ['guides'],
}

/**
 * Sections backed by a `format` rather than a `primaryType`.
 *
 * Guides are not a subject, they are a shape — a city guide about food is
 * still about food. §4 keeps that distinction, so this one section filters on
 * `format` and the rest filter on type.
 */
const FORMAT_SECTIONS: Record<string, string[]> = {
  guides: ['city-guide'],
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

/**
 * Maps docs to articles, repointing hero images at the URL that serves them.
 *
 * One batched query per call rather than one per article — a twelve-card home
 * page should cost one media lookup, not twelve. See `legacyMediaUrls` for why
 * the Local API cannot answer this.
 */
async function toArticles(docs: Record<string, unknown>[]): Promise<Article[]> {
  const urls = await legacyMediaUrls(
    docs.map(heroMediaId).filter((id): id is number => id !== null),
  )
  return docs.map((doc) => {
    const article = toArticle(doc)
    const id = heroMediaId(doc)
    const legacy = id === null ? undefined : urls.get(id)
    return legacy ? { ...article, image: legacy } : article
  })
}

export async function getLatest(limit = 20): Promise<Article[]> {
  const payload = await payloadClient()
  const { docs } = await payload.find({
    collection: 'articles',
    where: PUBLISHED,
    sort: '-publishedAt',
    limit,
    depth: 1, // resolves heroMedia to a document rather than an id
  })
  return toArticles(docs)
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
  const formats = FORMAT_SECTIONS[slug]
  const types = SECTION_TO_TYPES[slug]
  if (!formats && !types) return []

  const payload = await payloadClient()
  const { docs } = await payload.find({
    collection: 'articles',
    where: {
      ...PUBLISHED,
      ...(formats ? { format: { in: formats } } : { primaryType: { in: types } }),
      ...(format ? { format: { equals: format } } : {}),
    },
    sort: '-publishedAt',
    limit,
    depth: 1,
  })
  return toArticles(docs)
}

/**
 * Culture: the taxonomy terms that together make up the subject.
 *
 * There is no `culture` primaryType — see `TYPE_TO_SECTION` in payload.ts for
 * what happens when you pretend there is. These are real term slugs and are
 * verified present in the platform vocabulary; where a city has none tagged,
 * the page shows an empty state rather than an error.
 */
const CULTURE_TERMS = ['culture', 'heritage', 'people', 'art', 'music']

export async function getCulture(limit = 24): Promise<Article[]> {
  const ids = await articleIdsForTermSlugs(CULTURE_TERMS, 500)
  if (ids.length === 0) return []

  const payload = await payloadClient()
  const { docs } = await payload.find({
    collection: 'articles',
    where: { ...PUBLISHED, id: { in: ids } },
    sort: '-publishedAt',
    limit,
    depth: 1,
  })
  return toArticles(docs)
}

export type Facet = { label: string; value: string | null; count: number }

/**
 * Human labels for the `format` vocabulary.
 *
 * **Every key must exist in `enum_articles_format`**, which is exactly:
 *
 *     city-guide, event, feature, guide, heritage, listing, news, offer,
 *     opinion, people, review
 *
 * An earlier version invented `interview` and `listicle`. Neither exists, so
 * counting them sent an unknown label to Postgres and every section page
 * returned 500 — `invalid input value for enum enum_articles_format`. The
 * same mistake, in the same shape, as mapping a `culture` primaryType that
 * was never in the enum either.
 *
 * Unlabelled values still appear, humanised, rather than being dropped: the
 * counts come from the DATA, and a label table that silently hides a format
 * would make the facet row lie about what is in the section.
 */
const FORMAT_LABELS: Record<string, string> = {
  news: 'News',
  feature: 'Features',
  review: 'Reviews',
  'city-guide': 'City Guides',
  guide: 'Guides',
  offer: 'Offers',
  event: 'Events',
  people: 'People',
  opinion: 'Opinion',
  heritage: 'Heritage',
  listing: 'Listings',
}

function humanise(value: string): string {
  return FORMAT_LABELS[value] ?? value.replace(/-/g, ' ').replace(/^./, (c) => c.toUpperCase())
}

/**
 * Real facet counts for a section index, in ONE query.
 *
 * Counts are grouped in SQL rather than asked for one format at a time. The
 * previous shape issued a count per label — nine round trips for a page that
 * needs one — and, worse, it could only count formats someone had thought to
 * list. Grouping asks the data what is there, so a format added by the
 * classifier tomorrow appears without a code change and an invented one
 * cannot be sent at all.
 *
 * Uses the same city pool as `legacyMediaUrls`; see that function for why a
 * narrow direct read is preferred here over the Local API, which cannot
 * aggregate.
 */
export async function getSectionFacets(slug: string): Promise<Facet[]> {
  const formats = FORMAT_SECTIONS[slug]
  const types = SECTION_TO_TYPES[slug]
  if (!formats && !types) return []

  const rows = await sectionFormatCounts({ formats, types })
  const total = rows.reduce((sum, r) => sum + r.count, 0)

  return [
    { label: 'All', value: null, count: total },
    ...rows
      .filter((r) => r.format && r.count > 0)
      .map((r) => ({ label: humanise(r.format!), value: r.format, count: r.count }))
      .sort((a, b) => b.count - a.count),
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
  if (!docs[0]) return undefined
  const [article] = await toArticles([docs[0]])
  return article
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
