/**
 * The Payload Local API handle, and the row → view-model mapper.
 *
 * `docs/ui-data-layer.md` fixes the boundary and it is not negotiable:
 * articles, places, events and media come from the **Local API** against the
 * city database; ranked rails, search and facet counts come from
 * **engine-api**. A page may call both. A page may never query Postgres
 * directly, and may never re-rank what engine-api returned.
 *
 * Local rather than the REST endpoint because this app and the CMS bind to
 * the same city database: importing the config and calling
 * `getPayload({ config })` runs the query in-process — no network hop, no
 * serialisation, no second auth hop.
 *
 * **This app must never write.** Every helper here is a read.
 */

import configPromise from '@now-engine/cms/payload.config'
import pg from 'pg'
import { getPayload } from 'payload'

import type { Article } from '@/lib/content'
import { decodeEntities, sanitizeHtml, stripTags } from '@/lib/html'

/**
 * One Local API handle for the process.
 *
 * No cast here, and that is the point of the workspace: payload resolves to a
 * single install, so the config this returns and the config `getPayload`
 * expects are the same type. Before hoisting there were three copies of
 * payload@3.88.0 in the tree and TypeScript gave up comparing their
 * structurally identical `SanitizedConfig`s with "Excessive stack depth".
 */
export async function payloadClient() {
  return getPayload({ config: configPromise })
}

/**
 * Editorial section for a row, derived from the §4 L1 `primaryType`.
 *
 * **Every value here must exist in `enum_articles_primary_type`.** The real
 * vocabulary is exactly:
 *
 *     do, drink, eat, editorial, event, shop, stay, wellness, unknown
 *
 * An earlier version mapped `culture: 'culture'`, which is not one of them,
 * so /culture reached Postgres as a filter on a non-existent enum label and
 * returned 500 — `invalid input value for enum enum_articles_primary_type:
 * "culture"`. A section whose type does not exist is not an empty page, it is
 * a server error.
 *
 * Every value in that vocabulary now has a home. Earlier this mapped only the
 * seven venue-shaped types and let `editorial`, `unknown` and NULL fall
 * through to no section at all — which meant **half the archive was
 * unreachable by browsing**: 2,391 of Jakarta's 4,772 published articles and
 * 1,557 of Bali's 4,429 existed only at their direct URL.
 *
 * That was the right call while the plan was to classify everything before
 * launch. The plan is now the opposite: publish the whole archive, label
 * honestly what is not yet classified, and let editors re-file it in
 * team-editor. An article in `Unclassified` is visibly unsorted and one click
 * from being sorted; an article in no section is simply lost.
 *
 * `unknown` and NULL are handled in content.ts rather than here, because they
 * are the *absence* of a type — there is no key to map.
 */
const TYPE_TO_SECTION: Record<string, string> = {
  eat: 'dining',
  drink: 'dining',
  stay: 'stay',
  wellness: 'wellness',
  do: 'things-to-do',
  shop: 'things-to-do',
  event: 'events',
  editorial: 'editorial',
}

export function sectionForType(primaryType: string | null | undefined): string | null {
  if (!primaryType) return null
  return TYPE_TO_SECTION[primaryType] ?? null
}

export const SECTION_TO_TYPES: Record<string, string[]> = Object.entries(TYPE_TO_SECTION).reduce<
  Record<string, string[]>
>((acc, [type, section]) => {
  ;(acc[section] ??= []).push(type)
  return acc
}, {})

/**
 * `/%postname%/` → `postname`.
 *
 * LIVE_RECON confirmed both sites use a flat permalink at the domain root,
 * and those URLs are the traffic — so the stored `legacy_permalink` IS the
 * slug, not a derivation of the title. Deriving from the title instead would
 * silently break every inbound link whose title has since been edited.
 */
export function slugFromPermalink(permalink: string | null | undefined): string {
  if (!permalink) return ''
  return permalink.replace(/^\/+|\/+$/g, '')
}

type PayloadDoc = Record<string, unknown>

/**
 * Resolves hero images to the URL that actually serves them.
 *
 * **Why this bypasses the Local API, which the data-layer contract otherwise
 * forbids.** `media.url` holds the legacy WordPress URL these assets are
 * still served from — E1.3 has not mirrored the ~9 GB of uploads onto this
 * host — and `next.config.mjs` already allowlists those origins. But Payload
 * treats `media` as an upload collection it owns, so on read it REPLACES
 * `url` with `/api/media/file/<filename>`, a route backed by files that are
 * not there. Every image then 500s.
 *
 * `disableLocalStorage` does not change this; the URL is computed either way.
 * So the stored column is unreachable through the Local API, and one narrow
 * read is the honest way to get it.
 *
 * This is temporary and deletes itself: once E1.3 mirrors uploads into
 * Garage, Payload's own URL becomes correct and this whole module goes.
 */
let mediaPool: pg.Pool | null = null

export function cityPool(): pg.Pool {
  const connectionString = process.env.DATABASE_URI
  if (!connectionString) throw new Error('DATABASE_URI is not set')
  mediaPool ??= new pg.Pool({ connectionString, max: 2, statement_timeout: 5_000 })
  return mediaPool
}

export async function legacyMediaUrls(ids: number[]): Promise<Map<number, string>> {
  const unique = [...new Set(ids.filter((id) => Number.isFinite(id)))]
  if (unique.length === 0) return new Map()
  try {
    const { rows } = await cityPool().query(
      'SELECT id, url FROM public.media WHERE id = ANY($1) AND url IS NOT NULL',
      [unique],
    )
    return new Map(rows.map((r) => [Number(r.id), String(r.url)]))
  } catch {
    // A missing image is a worse page, not a broken one. Fall back to
    // whatever Payload produced rather than failing the render.
    return new Map()
  }
}

/** The hero media row id on a doc, whether it came back as an id or a document. */
export function heroMediaId(doc: PayloadDoc): number | null {
  const hero = doc.heroMedia
  if (typeof hero === 'number') return hero
  if (hero && typeof hero === 'object') {
    const id = (hero as PayloadDoc).id
    return typeof id === 'number' ? id : Number(id) || null
  }
  return null
}

function heroUrl(doc: PayloadDoc): string {
  const hero = doc.heroMedia as PayloadDoc | number | null | undefined
  if (!hero || typeof hero === 'number') return ''
  // `sizes.card` when the derivative exists, else the original. Never a
  // thumbnail: these are magazine cards, and an upscaled 150px crop looks
  // worse than a slightly heavy image.
  const sizes = hero.sizes as PayloadDoc | undefined
  const card = sizes?.card as PayloadDoc | undefined
  return String(card?.url ?? hero.url ?? '')
}

/**
 * Body paragraphs, sanitised here rather than at the point of render.
 *
 * The field is `html` and holds real markup. The reader printed it with
 * `<p>{p}</p>`, so React escaped it and readers saw
 * `<strong>Open daily from 5.30pm</strong>` and whole mailto anchors in the
 * middle of the copy — on every article with any formatting.
 *
 * Sanitising in the mapper means no page can forget to: a component receiving
 * `article.paras` is receiving vetted HTML by construction. See lib/html.ts
 * for the allowlist and why it is hand-written.
 */
function paragraphs(doc: PayloadDoc): string[] {
  const blocks = doc.bodyBlocks
  if (!Array.isArray(blocks)) return []
  return blocks
    .filter((b): b is PayloadDoc => Boolean(b) && (b as PayloadDoc).type === 'paragraph')
    .map((b) => sanitizeHtml(String(b.html ?? '')))
    .filter((html) => stripTags(html).length > 0)
}

/**
 * The one place a Payload row meets the view model. Pages must not learn what
 * a Payload document looks like — that is what keeps the source swappable,
 * and it is why every page survived this migration unchanged.
 */
export function toArticle(doc: PayloadDoc): Article {
  const primaryType = (doc.primaryType as string | null) ?? null
  return {
    id: Number(doc.id),
    // Decoded, not escaped-through. 81 Bali titles store entities — "Catch
    // &amp; Grill" — and a plain-text field renders them literally.
    title: decodeEntities(String(doc.title ?? '')),
    // The article's own slug is authoritative; the legacy permalink is the
    // fallback and, for the 9,201 imported articles, is what the slug was
    // backfilled *from* — so the two agree until someone edits one. Before
    // S1.1 this line read the permalink only, which meant a newly written
    // article mapped to `slug: ''` and every card linking to it pointed at
    // the homepage. Both addresses still resolve (`getBySlug`), so a legacy
    // URL survives an edit to this field.
    slug: (typeof doc.slug === 'string' && doc.slug !== '' ? doc.slug : null) ?? slugFromPermalink(doc.legacyPermalink as string | null),
    date: String(doc.publishedAt ?? doc.createdAt ?? ''),
    // The view model's `section` is the human-facing label the fixture era
    // stored; `sectionOf()` maps it to a slug. Feeding it the slug directly
    // is correct because `sectionOf` falls through to `slugify(section)`.
    // 'unclassified' is a real section now, so an untyped article gets a
    // working kicker link instead of 'more', which resolved to no route and
    // rendered a link to a 404 on every untyped card.
    section: sectionForType(primaryType) ?? 'unclassified',
    // Edition 2 (WS1): the §4 L1 type, exposed directly rather than only
    // implicitly through `categories[0]` — `getArticleRails`'s competitor
    // guard (`lib/competitorPolicy.ts`) needs it to check a rail candidate's
    // own type, and `categories` is a display list a future edit could
    // reorder or extend without anyone noticing it was secretly load-bearing.
    primaryType,
    categories: primaryType ? [primaryType] : [],
    tags: [],
    image: heroUrl(doc),
    // The dek is plain text in the view model (it becomes a meta description
    // and a card subtitle), so any stray markup is stripped rather than kept.
    // So are `%%…%%` template tokens: an old WordPress plugin's excerpt
    // placeholder (`%%cf_content%%`) was imported verbatim into Jakarta deks
    // and showed on 12 cards across the home page and /culture (QA,
    // 2026-09-25). The data still carries it; readers no longer see it.
    dek: stripTags(String(doc.dek ?? '')).replace(/%%[a-z0-9_]+%%\s*/gi, '').trim(),
    paras: paragraphs(doc),
    // Deliberately 0, never imported. §6: WordPress view counts are
    // bot-contaminated, and `getMostRead` must be recomputed from beacon data
    // rather than inheriting a number nobody can defend.
    views: 0,
  }
}

/**
 * Format counts for a section, grouped in SQL.
 *
 * The Local API cannot aggregate — `payload.count` answers one filter at a
 * time — so a facet row would otherwise cost one round trip per format and
 * could only ever count values someone hardcoded. Grouping asks the data
 * what formats are actually present, which is both cheaper and impossible to
 * drift from the enum.
 *
 * Only ever reads. Filters are parameterised; `slug` never reaches SQL.
 */
export async function sectionFormatCounts(
  filter: { formats?: string[]; types?: string[]; untyped?: boolean },
): Promise<Array<{ format: string | null; count: number }>> {
  const { formats, types, untyped } = filter
  try {
    // `untyped` cannot be a parameterised list: it is the absence of a value.
    // Both spellings count — NULL from the importer, `unknown` from the
    // classifier declining to guess.
    const where = untyped
      ? { clause: "(primary_type IS NULL OR primary_type::text = 'unknown')", param: null }
      : formats
        ? { clause: 'format::text = ANY($1)', param: formats }
        : { clause: 'primary_type::text = ANY($1)', param: types ?? [] }

    const { rows } = await cityPool().query(
      `SELECT format::text AS format, count(*)::int AS count
         FROM public.articles
        WHERE _status = 'published'
          AND published_at IS NOT NULL AND published_at <= now()
          AND ${where.clause}
        GROUP BY 1`,
      where.param === null ? [] : [where.param],
    )
    return rows.map((r) => ({ format: r.format, count: Number(r.count) }))
  } catch {
    // A section without its facet row is still a readable section.
    return []
  }
}

/**
 * Location terms with the number of published articles tagged to each.
 *
 * Areas are a PLATFORM concept — `engine.terms` joined to `engine.facets`
 * holds one taxonomy shared by every city (§4) — while the tagging itself,
 * `engine.entity_terms`, is per-city. So this needs both databases, which is
 * also why it cannot come from the Local API: that binds one.
 *
 * Terms with no articles are dropped rather than listed at zero. An index of
 * empty links is worse than a shorter index — it was a footer full of those
 * that made the site feel broken in the first place.
 */
export async function areasWithCounts(): Promise<
  Array<{ slug: string; label: string; count: number }>
> {
  const platformUrl = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!platformUrl) return []

  try {
    const { rows: counts } = await cityPool().query(
      `SELECT term_id::text AS term_id, count(DISTINCT entity_id)::int AS count
         FROM engine.entity_terms
        WHERE entity_type = 'article'
        GROUP BY 1`,
    )
    if (counts.length === 0) return []

    const platform = new pg.Pool({ connectionString: platformUrl, max: 2, statement_timeout: 5_000 })
    try {
      const { rows: terms } = await platform.query(
        `SELECT t.id::text AS id, t.slug, t.label
           FROM engine.terms t
           JOIN engine.facets f ON f.id = t.facet_id
          WHERE f.key = 'location'`,
      )
      const byId = new Map(counts.map((c) => [c.term_id, Number(c.count)]))
      return terms
        .map((t) => ({ slug: String(t.slug), label: String(t.label), count: byId.get(t.id) ?? 0 }))
        .filter((t) => t.count > 0)
        .sort((a, b) => b.count - a.count)
    } finally {
      await platform.end()
    }
  } catch {
    return []
  }
}

/**
 * Article ids carrying any of the given taxonomy term slugs.
 *
 * Culture is not a `primaryType` — the §4 L1 vocabulary has no such label,
 * and mapping one produced a 500 (see `TYPE_TO_SECTION` above). It exists in
 * the taxonomy instead, spread across the `subtype` and `format` facets as
 * culture / heritage / people / art / music. So a culture index is a term
 * lookup, not a column filter.
 *
 * Two connections for the same reason `areasWithCounts` needs two: the
 * vocabulary (`engine.terms` + `engine.facets`) is PLATFORM-level and shared
 * by every city, while the tagging (`engine.entity_terms`) is per-city.
 *
 * Slugs, not ids: a term id is a UUID generated at seed time and differs
 * between environments, so hardcoding one would work here and break on
 * helios. Slugs are the stable key.
 */
export async function articleIdsForTermSlugs(slugs: string[], limit = 200): Promise<number[]> {
  const platformUrl = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!platformUrl || slugs.length === 0) return []

  try {
    const platform = new pg.Pool({ connectionString: platformUrl, max: 2, statement_timeout: 5_000 })
    let termIds: string[]
    try {
      const { rows } = await platform.query(
        `SELECT t.id::text AS id
           FROM engine.terms t
           JOIN engine.facets f ON f.id = t.facet_id
          WHERE t.slug = ANY($1) AND f.key = ANY($2)`,
        [slugs, ['subtype', 'format', 'topic']],
      )
      termIds = rows.map((r) => String(r.id))
    } finally {
      await platform.end()
    }
    if (termIds.length === 0) return []

    const { rows } = await cityPool().query(
      `SELECT DISTINCT entity_id
         FROM engine.entity_terms
        WHERE entity_type = 'article' AND term_id = ANY($1::uuid[])
        LIMIT $2`,
      [termIds, limit],
    )
    return rows.map((r) => Number(r.entity_id)).filter(Number.isFinite)
  } catch {
    // An index that cannot reach the taxonomy is empty, not broken.
    return []
  }
}

export type PlaceRow = {
  /** `public.places.id` — what the beacon reports as `entity_id` (E8.5), and
   *  what `entity_terms` and `partnerships.place_id` join on. The slug is the
   *  URL, not the key. */
  id: string
  slug: string
  name: string
  area: string | null
  type: string | null
  subtype: string | null
  priceBand: string | null
  address: string | null
}

/**
 * Published venues.
 *
 * **`status = 'active'` is the whole point of this function.** All 6,589
 * Jakarta and 5,918 Bali places are still `pending_review` (F27, recorded as
 * launch-blocking), and a public index that ignored `status` would publish
 * twelve thousand unverified venue records — addresses, prices and opening
 * claims nobody has checked — under NOW!'s name. So this returns an empty
 * list today and fills in on its own as review progresses. That is the
 * correct behaviour, not a gap to work around.
 */
export async function activePlaces(limit = 120): Promise<PlaceRow[]> {
  try {
    const { rows } = await cityPool().query(
      `SELECT id::text AS id, slug, name, area_term::text AS area, type::text AS type,
              subtype::text AS subtype, price_band::text AS price_band, address
         FROM public.places
        WHERE status = 'active' AND slug IS NOT NULL
        ORDER BY name
        LIMIT $1`,
      [limit],
    )
    return rows.map((r) => ({
      id: String(r.id),
      slug: String(r.slug),
      // Decoded in the helper, not at each call site, so no page can forget.
      name: decodeEntities(String(r.name)),
      area: r.area ? String(r.area) : null,
      type: r.type ? String(r.type) : null,
      subtype: r.subtype ? String(r.subtype) : null,
      priceBand: r.price_band ? String(r.price_band) : null,
      address: r.address ? String(r.address) : null,
    }))
  } catch {
    return []
  }
}

/** How many venues exist at all, and how many are still awaiting review. */
export async function placeReviewCounts(): Promise<{ total: number; pending: number }> {
  try {
    const { rows } = await cityPool().query(
      `SELECT count(*)::int AS total,
              count(*) FILTER (WHERE status = 'pending_review')::int AS pending
         FROM public.places`,
    )
    return { total: Number(rows[0]?.total ?? 0), pending: Number(rows[0]?.pending ?? 0) }
  } catch {
    return { total: 0, pending: 0 }
  }
}

/**
 * One venue by slug — **only if it is `active`**.
 *
 * Returns null for a `pending_review` row so the profile 404s rather than
 * publishing unchecked facts. Same reasoning as `activePlaces`, and it has to
 * be enforced here too: a directory that hides a venue while its profile
 * still serves the address has not hidden anything.
 */
export async function activePlaceBySlug(slug: string): Promise<PlaceRow | null> {
  try {
    const { rows } = await cityPool().query(
      `SELECT id::text AS id, slug, name, area_term::text AS area, type::text AS type,
              subtype::text AS subtype, price_band::text AS price_band, address
         FROM public.places
        WHERE slug = $1 AND status = 'active'
        LIMIT 1`,
      [slug],
    )
    const r = rows[0]
    if (!r) return null
    return {
      id: String(r.id),
      slug: String(r.slug),
      name: decodeEntities(String(r.name)),
      area: r.area ? String(r.area) : null,
      type: r.type ? String(r.type) : null,
      subtype: r.subtype ? String(r.subtype) : null,
      priceBand: r.price_band ? String(r.price_band) : null,
      address: r.address ? String(r.address) : null,
    }
  } catch {
    return null
  }
}


export type AreaTerm = { slug: string; label: string; count: number }
export type AreaRegion = AreaTerm & { areas: AreaTerm[] }
export type AreaTree = {
  /** This city, with its sub-regions. Empty when the registry has no term
   *  matching the site slug. */
  local: { label: string; total: number; own: AreaTerm | null; regions: AreaRegion[] }
  /** The rest of Indonesia — the sibling city and the national catch-all. */
  indonesia: AreaTerm[]
  /** Everywhere else. */
  international: AreaTerm[]
}

/**
 * The location taxonomy as a tree, split into this city / rest of Indonesia /
 * international.
 *
 * `/areas` used to render one flat, count-sorted list of every location term
 * with any coverage. On Bali that put BALI, UBUD and SEMINYAK next to EUROPE,
 * JAPAN and NORTH JAKARTA in a single wall of 90-odd chips — technically
 * accurate and useless as a way to find a neighbourhood.
 *
 * The taxonomy already has the shape needed: `indonesia` and `international`
 * are roots, `bali` and `jakarta` sit under `indonesia`, and each city's
 * sub-regions sit under it. So this is a grouping problem, not a data problem.
 *
 * The city is taken from the SITE CONFIG's slug, never a literal — §3.5, and
 * `npm run lint:site-literals` enforces it. If no location term matches that
 * slug the local group comes back empty rather than guessing, and the page
 * still renders the other two.
 */
export async function locationTree(citySlug: string): Promise<AreaTree> {
  const empty: AreaTree = {
    local: { label: '', total: 0, own: null, regions: [] },
    indonesia: [],
    international: [],
  }
  const platformUrl = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!platformUrl) return empty

  try {
    const { rows: counts } = await cityPool().query(
      `SELECT term_id::text AS term_id, count(DISTINCT entity_id)::int AS count
         FROM engine.entity_terms
        WHERE entity_type = 'article'
        GROUP BY 1`,
    )
    const countById = new Map<string, number>(counts.map((c) => [String(c.term_id), Number(c.count)]))

    const platform = new pg.Pool({ connectionString: platformUrl, max: 2, statement_timeout: 5_000 })
    let terms: Array<{ id: string; slug: string; label: string; parent: string | null }>
    try {
      const { rows } = await platform.query(
        `SELECT t.id::text AS id, t.slug, t.label, t.parent_id::text AS parent
           FROM engine.terms t
           JOIN engine.facets f ON f.id = t.facet_id
          WHERE f.key = 'location'`,
      )
      terms = rows.map((r) => ({
        slug: String(r.slug),
        label: String(r.label),
        id: String(r.id),
        parent: r.parent ? String(r.parent) : null,
      }))
    } finally {
      await platform.end()
    }
    if (terms.length === 0) return empty

    const byId = new Map(terms.map((t) => [t.id, t]))
    const childrenOf = new Map<string | null, typeof terms>()
    for (const t of terms) {
      const list = childrenOf.get(t.parent) ?? []
      list.push(t)
      childrenOf.set(t.parent, list)
    }
    const toTerm = (t: (typeof terms)[number]): AreaTerm => ({
      slug: t.slug,
      label: t.label,
      count: countById.get(t.id) ?? 0,
    })
    // Counts include descendants, so a region reads as the whole region rather
    // than as whatever happens to be tagged at exactly that level.
    const subtreeCount = (id: string): number => {
      let total = countById.get(id) ?? 0
      for (const child of childrenOf.get(id) ?? []) total += subtreeCount(child.id)
      return total
    }

    const city = terms.find((t) => t.slug === citySlug)
    const indonesiaRoot = terms.find((t) => t.slug === 'indonesia' && t.parent === null)
    const internationalRoot = terms.find((t) => t.slug === 'international' && t.parent === null)

    const byCountThenLabel = (a: AreaTerm, b: AreaTerm) =>
      b.count - a.count || a.label.localeCompare(b.label)

    const regions: AreaRegion[] = city
      ? (childrenOf.get(city.id) ?? [])
          .map((region) => ({
            slug: region.slug,
            label: region.label,
            count: subtreeCount(region.id),
            areas: (childrenOf.get(region.id) ?? [])
              .map(toTerm)
              .filter((a) => a.count > 0)
              .sort(byCountThenLabel),
          }))
          .filter((r) => r.count > 0 || r.areas.length > 0)
          .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
      : []

    // The sibling city and the national catch-all, minus this city itself.
    const indonesia = indonesiaRoot
      ? (childrenOf.get(indonesiaRoot.id) ?? [])
          .filter((t) => t.slug !== citySlug)
          .map((t) => ({ ...toTerm(t), count: subtreeCount(t.id) }))
          .filter((t) => t.count > 0)
          .sort(byCountThenLabel)
      : []

    const international = internationalRoot
      ? (childrenOf.get(internationalRoot.id) ?? [])
          .map((t) => ({ ...toTerm(t), count: subtreeCount(t.id) }))
          .filter((t) => t.count > 0)
          .sort(byCountThenLabel)
      : []

    return {
      local: {
        label: city?.label ?? '',
        total: city ? subtreeCount(city.id) : 0,
        own: city ? toTerm(city) : null,
        regions,
      },
      indonesia,
      international,
    }
  } catch {
    // An index that cannot reach the taxonomy is empty, not broken.
    return empty
  }
}

export type ArchiveStats = {
  articles: number
  sinceYear: number | null
  authors: number
  areas: number
}

/**
 * Real numbers for the pages that describe the publication.
 *
 * About and Advertise need to say something concrete, and the honest source
 * is the archive itself rather than a figure someone typed once and nobody
 * revisited. Bali has published since 2013 and Jakarta since 2019; both
 * numbers grow on their own, and neither can go stale in a way that misleads.
 *
 * Deliberately NOT audience figures. We have no measured readership — the
 * beacon is not live (§6, and `views` is hardcoded to 0 for the same reason)
 * — so any traffic claim on an Advertise page would be invented. What we can
 * state truthfully is the size and reach of the archive.
 */
export async function archiveStats(): Promise<ArchiveStats> {
  const zero: ArchiveStats = { articles: 0, sinceYear: null, authors: 0, areas: 0 }
  try {
    const { rows } = await cityPool().query(
      `SELECT count(*)::int AS articles,
              EXTRACT(YEAR FROM min(published_at))::int AS since_year
         FROM public.articles
        WHERE _status = 'published'
          AND published_at IS NOT NULL AND published_at <= now()`,
    )
    const { rows: authorRows } = await cityPool().query(
      'SELECT count(*)::int AS n FROM public.authors',
    )
    const { rows: areaRows } = await cityPool().query(
      `SELECT count(DISTINCT term_id)::int AS n
         FROM engine.entity_terms WHERE entity_type = 'article'`,
    )
    return {
      articles: Number(rows[0]?.articles ?? 0),
      sinceYear: rows[0]?.since_year ? Number(rows[0].since_year) : null,
      authors: Number(authorRows[0]?.n ?? 0),
      areas: Number(areaRows[0]?.n ?? 0),
    }
  } catch {
    return zero
  }
}
