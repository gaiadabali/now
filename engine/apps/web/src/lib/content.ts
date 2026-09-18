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
  cityPool,
  heroMediaId,
  legacyMediaUrls,
  payloadClient,
  sectionFormatCounts,
  toArticle,
} from '@/lib/payload'
import { slugify } from '@/lib/format'
import { decodeEntities } from '@/lib/html'

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
  editorial: ['editorial'],
  unclassified: ['unclassified'],
}

/**
 * The section for articles the classifier has not typed.
 *
 * `primaryType` is NULL for 1,183 published Jakarta articles and 799 in Bali,
 * and `unknown` is the fail-closed sentinel for the same condition. Before
 * this section existed they were reachable only by their direct URL — a
 * quarter of the archive, invisible to anyone browsing.
 *
 * Naming it plainly is deliberate. These are not miscellaneous articles, they
 * are unsorted ones, and an editor opening `Unclassified` in team-editor
 * knows exactly what the queue is. Calling it "More" would hide the backlog
 * behind a word that sounds intentional.
 */
export const UNCLASSIFIED = 'unclassified'

/**
 * The `?format=` value meaning "has no format".
 *
 * A sentinel is needed because absence cannot be expressed as a value in a
 * query string, and `?format=` with an empty value is indistinguishable from
 * the parameter being absent — which means All. Chosen to be something no
 * `enum_articles_format` label could ever collide with.
 */
export const NO_FORMAT = '__none'

/**
 * Both format terms that mean "guide".
 *
 * The vocabulary carries `city-guide` ("City guide") and `guide` ("Guide") as
 * separate format terms, with no description distinguishing them. The Guides
 * section filtered on `city-guide` alone, and that split cost Bali most of its
 * guides: the section showed **51 of 230**, and the other 179 were reachable
 * only at their direct URL. Jakarta showed 267 of 314.
 *
 * Two sibling terms that both mean guide belong in the section called Guides.
 * The same reasoning produced the `Unclassified` section for the 1,183
 * untyped articles that were invisible to anyone browsing — an archive you
 * cannot reach is not an archive. If the taxonomy review later draws a real
 * distinction between the two terms, this constant is the one line that
 * changes, and it is the single source for both the section and the homepage
 * rail.
 */
const GUIDE_FORMATS = ['city-guide', 'guide']

/**
 * Sections backed by a `format` rather than a `primaryType`.
 *
 * Guides are not a subject, they are a shape — a city guide about food is
 * still about food. §4 keeps that distinction, so this one section filters on
 * `format` and the rest filter on type.
 */
const FORMAT_SECTIONS: Record<string, string[]> = {
  guides: GUIDE_FORMATS,
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

const SECTION_LABELS: Record<string, string> = {
  'things-to-do': 'Things to Do',
  unclassified: 'Unclassified',
  editorial: 'Editorial',
}

export function sectionLabel(slug: string): string {
  return (
    SECTION_LABELS[slug] ??
    slug
      .split('-')
      .map((w) => w[0].toUpperCase() + w.slice(1))
      .join(' ')
  )
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

export type Page<T> = {
  items: T[]
  page: number
  totalPages: number
  total: number
}

/**
 * The `where` clause that selects a section's articles.
 *
 * Unclassified is the interesting one: it is defined by the ABSENCE of a
 * type, so it cannot be expressed as `primaryType: { in: [...] }`. Both
 * spellings of "not classified" have to be caught — NULL, which is what the
 * importer left, and the `unknown` enum label, which is what the classifier
 * writes when it declines to guess. Matching only one would strand the other,
 * and which one a row carries is an accident of which pipeline touched it.
 */
function sectionWhere(slug: string): Record<string, unknown> | null {
  if (slug === UNCLASSIFIED) {
    return {
      or: [{ primaryType: { exists: false } }, { primaryType: { equals: 'unknown' } }],
    }
  }
  const formats = FORMAT_SECTIONS[slug]
  if (formats) return { format: { in: formats } }
  const types = SECTION_TO_TYPES[slug]
  if (types) return { primaryType: { in: types } }
  return null
}

/**
 * One page of the whole archive, newest first.
 *
 * `/latest` was linked twice from the homepage and 404'd both times: it is not
 * in `SECTION_MAP`, so `isSectionSlug` was false and `[slug]` looked it up as
 * an article, found nothing, and called `notFound()`. A broken `<Link>` is
 * only wrong at click time, which is why it survived.
 *
 * Given the choice between deleting the links and making them work, this is
 * the archive: 4,772 and 4,429 articles with no cross-section index at all.
 * Every section has one; the union of them did not.
 */
export async function getArchivePage(opts: { page?: number; limit?: number } = {}): Promise<Page<Article>> {
  const { page = 1, limit = 24 } = opts
  const payload = await payloadClient()
  const result = await payload.find({
    collection: 'articles',
    where: PUBLISHED,
    sort: '-publishedAt',
    page: Math.max(1, page),
    limit,
    depth: 1,
  })
  return {
    items: await toArticles(result.docs),
    page: result.page ?? 1,
    totalPages: result.totalPages ?? 1,
    total: result.totalDocs ?? 0,
  }
}

/**
 * One page of a section.
 *
 * Paginated because the archive is the point. A section index that showed a
 * fixed twelve exposed 12 of Jakarta's 935 dining articles — the other 923
 * existed only at their direct URL, which is no way to hand an archive to an
 * editor. Payload counts and slices in one query, so the total costs nothing
 * extra and the page can say how much there is.
 */
export async function getSectionPage(
  slug: string,
  opts: { page?: number; limit?: number; format?: string } = {},
): Promise<Page<Article>> {
  const { page = 1, limit = 24, format } = opts
  const where = sectionWhere(slug)
  if (!where) return { items: [], page: 1, totalPages: 0, total: 0 }

  const payload = await payloadClient()
  const result = await payload.find({
    collection: 'articles',
    where: {
      ...PUBLISHED,
      ...where,
      ...(format
        ? format === NO_FORMAT
          ? { format: { exists: false } }
          : { format: { equals: format } }
        : {}),
    },
    sort: '-publishedAt',
    // A page past the end returns empty rather than throwing; the page
    // component turns that into a 404 so a bad ?page= cannot look like a
    // section that has run dry.
    page: Math.max(1, page),
    limit,
    depth: 1,
  })
  return {
    items: await toArticles(result.docs),
    page: result.page ?? 1,
    totalPages: result.totalPages ?? 1,
    total: result.totalDocs ?? 0,
  }
}

/** First page only — for rails and anywhere a count is not wanted. */
export async function getBySection(
  slug: string,
  limit = 12,
  format?: string,
): Promise<Article[]> {
  const { items } = await getSectionPage(slug, { limit, format })
  return items
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
  // Unclassified has neither — it is defined by the absence of a type — so it
  // needs its own branch or it would silently render no facet row at all.
  if (!formats && !types && slug !== UNCLASSIFIED) return []

  const rows = await sectionFormatCounts(
    slug === UNCLASSIFIED ? { untyped: true } : { formats, types },
  )
  const total = rows.reduce((sum, r) => sum + r.count, 0)

  // The untyped bucket is a CHIP, not a dropped row.
  //
  // It used to be filtered out by `r.format && ...`, so Bali's dining index
  // read "ALL 1251" above chips summing to 739 — the 512 articles with no
  // format were counted in the total and then discarded, which reads as an
  // arithmetic error on the page. They are also the ones editors most need to
  // find, since an unformatted article is unfiled work.
  const unformatted = rows.find((r) => !r.format)?.count ?? 0

  return [
    { label: 'All', value: null, count: total },
    ...rows
      .filter((r) => r.format && r.count > 0)
      .map((r) => ({ label: humanise(r.format!), value: r.format, count: r.count }))
      .sort((a, b) => b.count - a.count),
    ...(unformatted > 0
      ? [{ label: 'Unformatted', value: NO_FORMAT, count: unformatted }]
      : []),
  ]
}


/**
 * One address, two places it can be recorded.
 *
 * **Why both, and in this order.** The 9,201 imported articles are addressed
 * by `legacyPermalink`, and those URLs *are* the traffic (LIVE_RECON) — they
 * must keep resolving forever, which is why that field is marked DO NOT EDIT
 * in the CMS. But an article written today has no legacy permalink, and
 * before S1.1 there was no other field to address it by, so it was
 * unreachable. `slug` is now that field.
 *
 * `slug` is tried first because it is the one a writer controls and the one
 * new work uses. `legacyPermalink` is tried second, as an OR rather than a
 * fallback-on-empty, so that editing a legacy article's slug adds an address
 * instead of replacing one: the old URL a reader bookmarked in 2019 still
 * lands, and so does the new one. Migration
 * `20260918_090000_articles_slug` seeded every existing slug from its own
 * permalink, so for the whole archive the two queries agree and the second
 * one never fires.
 *
 * Two queries rather than one `or`, because Payload's `or` across two indexed
 * text fields plans as a bitmap OR over the whole table on Postgres, while
 * each of these is a single index hit on a unique or near-unique column. The
 * second only runs for an address the first did not answer.
 */
export async function getBySlug(slug: string, opts: { draft?: boolean } = {}): Promise<Article | undefined> {
  const payload = await payloadClient()

  // Preview (S4). `draft: true` makes Payload return the newest version of
  // each document rather than the published row, and the `_status` filter has
  // to come off with it or a never-published draft is excluded by the very
  // clause that protects everyone else.
  //
  // The ONLY caller that may pass this is the article page, and only when
  // Next's draft mode is enabled — which `/preview` turns on after checking a
  // staff session. A default of `false` here means every other surface (rails,
  // sections, search, the home page) keeps asking for published content and
  // cannot be talked into showing a draft by a query parameter.
  const status = opts.draft ? {} : PUBLISHED
  const find = { limit: 1, depth: 1, ...(opts.draft ? { draft: true } : {}) }

  const bySlug = await payload.find({
    collection: 'articles',
    where: { ...status, slug: { equals: slug } },
    ...find,
  })
  const doc =
    bySlug.docs[0] ??
    (
      await payload.find({
        collection: 'articles',
        where: { ...status, legacyPermalink: { equals: `/${slug}/` } },
        ...find,
      })
    ).docs[0]

  if (!doc) return undefined
  const [article] = await toArticles([doc])
  return article
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
/**
 * Sections worth recommending, in the order a reader is offered them.
 *
 * `unclassified` is absent on purpose: it is the editors' work queue, not a
 * recommendation. `editorial` sits last — it is real coverage, but a reader
 * who has just finished a restaurant review is better served by somewhere to
 * stay than by general commentary.
 */
const RECOMMEND_ORDER = ['stay', 'things-to-do', 'events', 'dining', 'wellness', 'guides', 'editorial']

/**
 * Read Next — deliberately NOT more of the same.
 *
 * This used to call `getBySection(sectionOf(article))`, which recommended the
 * one thing a reader demonstrably already has: an article about Raja's
 * Balinese Cuisine offered three more restaurants. A reader finishing a
 * restaurant review has chosen where to eat. What they have not chosen is
 * where to stay, what to do, or what is on.
 *
 * So the current section is excluded outright, and the remainder is taken
 * round-robin so three results come from three DIFFERENT sections rather than
 * three from whichever one happens to have published most recently.
 *
 * One query, not one per section: fetch a generous recent slice with the
 * article's own types excluded in SQL, then spread it here. An article page
 * should not cost six round trips to fill a rail of three.
 *
 * The rotation is seeded from the article id so that two dining articles
 * published the same week do not show an identical rail, while any single
 * article stays stable across renders — this is server-rendered and cached,
 * so randomness would mean a rail that changes under the reader.
 */
export async function getRelated(article: Article, limit = 3): Promise<Article[]> {
  const section = sectionOf(article)
  const pool = RECOMMEND_ORDER.filter((s) => s !== section)
  if (pool.length === 0) return []

  // One small query PER SECTION, in parallel, rather than one big recent slice.
  //
  // The single-query version was cheaper but could not guarantee variety: it
  // took the 60 most recent non-dining articles and spread those, so when
  // recent publishing clustered — as it does — a dining article got two
  // wellness recommendations out of three. Asking each section directly
  // guarantees one from each, which is the actual requirement. Six queries of
  // two rows, issued together, cost less than the media batch that follows.
  const perSection = await Promise.all(
    pool.map(async (key) => {
      const types = SECTION_TO_TYPES[key]
      const formats = FORMAT_SECTIONS[key]
      if (!types && !formats) return [] as Article[]
      const payload = await payloadClient()
      const { docs } = await payload.find({
        collection: 'articles',
        where: {
          and: [
            PUBLISHED,
            { id: { not_equals: article.id } },
            formats ? { format: { in: formats } } : { primaryType: { in: types } },
          ],
        },
        sort: '-publishedAt',
        limit: 2,
        depth: 1,
      })
      return toArticles(docs)
    }),
  )

  const available = pool
    .map((key, i) => [key, perSection[i]] as const)
    .filter(([, items]) => items.length > 0)
  if (available.length === 0) return []

  // Rotate by article id so two dining pieces published the same week do not
  // carry an identical rail, while any one article stays stable across
  // renders — this is server-rendered and cached, so randomness would mean a
  // rail that shifts under the reader.
  const rotation = article.id % available.length
  const rotated = [...available.slice(rotation), ...available.slice(0, rotation)]

  const picked: Article[] = []
  const seen = new Set<number>()
  for (let round = 0; picked.length < limit && round < 2; round++) {
    for (const [, items] of rotated) {
      const candidate = items[round]
      if (!candidate || seen.has(candidate.id)) continue
      seen.add(candidate.id)
      picked.push(candidate)
      if (picked.length === limit) break
    }
  }
  return picked
}


/* ========================================================================== */
/*  WHAT THE HOMEPAGE'S REMAINING RAILS ACTUALLY HAVE (S2)                    */
/* ========================================================================== */

/**
 * The comp-phase fixtures are gone, and so is what they were hiding.
 *
 * `src/fixtures/editorial.ts` supplied `GUIDES` (four guides with counts its
 * own comment called "illustrative") and `EVENTS` (four events, all of them in
 * one city, hardcoded to 2026 dates). Both rendered on both cities, so Jakarta
 * readers were shown a festival in Ubud. That is the kind of thing that is
 * invisible in a code review and obvious on the page.
 *
 * The three functions below replace them with the archive. Two of them can
 * return nothing, and the homepage renders no rail when they do — which is
 * the point of doing this before any redesign. Measured 2026-09-18:
 *
 *   guides            314 Jakarta · 230 Bali        a real rail
 *   upcoming events     0 Jakarta ·   0 Bali        every event is 2016–2020
 *   most read          63 interactions, one city    not a ranking yet
 *
 * So the honest homepage today has one of those three rails, not three. The
 * precedent for hiding rather than showing an empty one is `areasWithCounts`,
 * which drops terms with no articles because "an index of empty links is worse
 * than a shorter index — it was a footer full of those that made the site feel
 * broken in the first place".
 */

/**
 * The guides rail — the same `GUIDE_FORMATS` the `/guides` section uses, so
 * the rail and the page it links to can never disagree about what a guide is.
 */
export async function getGuides(limit = 4): Promise<Article[]> {
  const payload = await payloadClient()
  const { docs } = await payload.find({
    collection: 'articles',
    where: { ...PUBLISHED, format: { in: GUIDE_FORMATS } },
    sort: '-publishedAt',
    limit,
    depth: 1,
  })
  return toArticles(docs)
}

export type EventItem = {
  id: number
  title: string
  date: string
  where: string | null
  ticketUrl: string | null
}

/**
 * What is actually on, which today is nothing.
 *
 * Every published event in both cities starts between 2016-07-01 and
 * 2020-06-26 — they came across in the WordPress import and none has been
 * superseded. `starts_at >= now()` therefore returns zero rows, and the rail
 * disappears until an editor publishes a real one. That is the correct
 * behaviour and it is also the finding: the fixture existed because there is
 * no upcoming-event data, and deleting the fixture is what makes that visible
 * instead of papering over it.
 *
 * `rrule` is deliberately ignored. A recurring event whose series began in
 * 2018 may well have an occurrence next Tuesday, but expanding a recurrence
 * rule is real work with real edge cases, and guessing at it would put dates
 * on the page that nobody has checked — which is the fixture's failure mode
 * with extra steps. Tracked for the events surface rather than done here.
 */
export async function getUpcomingEvents(limit = 4): Promise<EventItem[]> {
  const payload = await payloadClient()
  const { docs } = await payload.find({
    collection: 'events',
    where: { ...PUBLISHED, startsAt: { greater_than_equal: new Date().toISOString() } },
    sort: 'startsAt',
    limit,
    depth: 1, // resolves `place` so the rail can say where
  })

  return docs.map((doc) => {
    const place = doc.place as { name?: unknown; areaTerm?: unknown } | number | null | undefined
    const name = place && typeof place === 'object' && typeof place.name === 'string' ? place.name : null
    const area = place && typeof place === 'object' && typeof place.areaTerm === 'string' ? place.areaTerm : null
    return {
      id: Number(doc.id),
      title: decodeEntities(String(doc.title ?? '')),
      date: String(doc.startsAt ?? ''),
      where: [name, area].filter(Boolean).join(', ') || null,
      ticketUrl: typeof doc.ticketUrl === 'string' ? doc.ticketUrl : null,
    }
  })
}

/**
 * How much behavioural signal a "Most Read" rail needs before it is one.
 *
 * The beacon went live on 2026-09-16 and has collected 63 interactions on one
 * city. Ranking five articles out of 63 events — most of them from the people
 * who built the thing — would put a number on the page that nobody can defend,
 * which is the exact objection §6 raises to importing WordPress's
 * bot-contaminated `wpb_post_views_count`.
 *
 * So the rail has a floor, and below it there is no rail. The numbers are
 * modest on purpose: this is a threshold for "is this signal or is this us",
 * not a statistical claim. It will pass on its own once the site has readers,
 * with no code change, which is the property that matters.
 */
const MOST_READ_MIN_INTERACTIONS = 500
const MOST_READ_WINDOW_DAYS = 30

/**
 * Most read, from revealed behaviour — or nothing at all.
 *
 * This used to be `return getLatest(limit)` under a rail labelled "Most Read".
 * The comment was honest about it and the page was not, which is the worse
 * half: a reader cannot see the comment. Recency presented as popularity is an
 * invented ranking, and §10's presentation-bias warning cuts exactly here —
 * a surface that claims an ordering it did not compute trains the eventual
 * ranker on a lie.
 *
 * Reads `engine.interactions` directly rather than through the API because
 * that table is in this city's own database and the query is a count, not a
 * ranking the engine owns. It is partitioned by day, so the window bound is
 * also the partition pruner.
 */
export async function getMostRead(limit = 5): Promise<Article[]> {
  let ids: number[] = []
  try {
    const { rows } = await cityPool().query(
      `WITH windowed AS (
         SELECT entity_id, count(*)::int AS n
           FROM engine.interactions
          WHERE entity_type = 'article'
            AND ts >= now() - ($1 || ' days')::interval
          GROUP BY entity_id
       )
       SELECT entity_id, n, sum(n) OVER ()::int AS total
         FROM windowed
        ORDER BY n DESC
        LIMIT $2`,
      [MOST_READ_WINDOW_DAYS, limit],
    )
    if (rows.length === 0 || Number(rows[0].total) < MOST_READ_MIN_INTERACTIONS) return []
    ids = rows.map((r) => Number(r.entity_id)).filter(Number.isFinite)
  } catch {
    // The rail is a nicety; the homepage is not. A partition that does not
    // exist yet, or a column type this query guessed wrong, must not 500 the
    // front page.
    return []
  }
  if (ids.length === 0) return []

  const payload = await payloadClient()
  const { docs } = await payload.find({
    collection: 'articles',
    where: { ...PUBLISHED, id: { in: ids } },
    limit,
    depth: 1,
  })
  const articles = await toArticles(docs)
  // Payload returns them in its own order; the ranking is the point.
  const rank = new Map(ids.map((id, i) => [id, i]))
  return articles.sort((a, b) => (rank.get(a.id) ?? 99) - (rank.get(b.id) ?? 99))
}
