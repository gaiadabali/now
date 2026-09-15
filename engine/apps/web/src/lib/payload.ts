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
 * Note what is deliberately NOT mapped:
 *   editorial  the catch-all (1,208 Jakarta articles). Putting it behind a
 *              named section would label general copy as that subject.
 *   unknown    the fail-closed sentinel for unclassified rows.
 *   (null)     E2 has not classified everything; 1,183 Jakarta rows are
 *              still untyped and belong in no section rather than a wrong one.
 *
 * The fixture era derived this from legacy WordPress category *names*, which
 * do not exist as a column — the archive's categories became taxonomy terms
 * during E1/E2. `primaryType` is the durable replacement and is what the
 * classifier actually populates.
 *
 * `editorial`, `event` and NULL deliberately fall through to `null` rather
 * than being forced into a section: 1,183 Jakarta articles are still
 * unclassified (E2 is not finished), and putting them in an arbitrary section
 * would be worse than leaving them out of section indexes, where they are
 * merely absent rather than wrong.
 */
const TYPE_TO_SECTION: Record<string, string> = {
  eat: 'dining',
  drink: 'dining',
  stay: 'stay',
  wellness: 'wellness',
  do: 'things-to-do',
  shop: 'things-to-do',
  event: 'events',
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

function cityPool(): pg.Pool {
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

function paragraphs(doc: PayloadDoc): string[] {
  const blocks = doc.bodyBlocks
  if (!Array.isArray(blocks)) return []
  return blocks
    .filter((b): b is PayloadDoc => Boolean(b) && (b as PayloadDoc).type === 'paragraph')
    .map((b) => String(b.html ?? ''))
    .filter(Boolean)
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
    title: String(doc.title ?? ''),
    slug: slugFromPermalink(doc.legacyPermalink as string | null),
    date: String(doc.publishedAt ?? doc.createdAt ?? ''),
    // The view model's `section` is the human-facing label the fixture era
    // stored; `sectionOf()` maps it to a slug. Feeding it the slug directly
    // is correct because `sectionOf` falls through to `slugify(section)`.
    section: sectionForType(primaryType) ?? 'more',
    categories: primaryType ? [primaryType] : [],
    tags: [],
    image: heroUrl(doc),
    dek: String(doc.dek ?? ''),
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
  filter: { formats?: string[]; types?: string[] },
): Promise<Array<{ format: string | null; count: number }>> {
  const { formats, types } = filter
  try {
    const where = formats
      ? { clause: 'format::text = ANY($1)', param: formats }
      : { clause: 'primary_type::text = ANY($1)', param: types ?? [] }

    const { rows } = await cityPool().query(
      `SELECT format::text AS format, count(*)::int AS count
         FROM public.articles
        WHERE _status = 'published'
          AND published_at IS NOT NULL AND published_at <= now()
          AND ${where.clause}
        GROUP BY 1`,
      [where.param],
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
      `SELECT slug, name, area_term::text AS area, type::text AS type,
              subtype::text AS subtype, price_band::text AS price_band, address
         FROM public.places
        WHERE status = 'active' AND slug IS NOT NULL
        ORDER BY name
        LIMIT $1`,
      [limit],
    )
    return rows.map((r) => ({
      slug: String(r.slug),
      name: String(r.name),
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
      `SELECT slug, name, area_term::text AS area, type::text AS type,
              subtype::text AS subtype, price_band::text AS price_band, address
         FROM public.places
        WHERE slug = $1 AND status = 'active'
        LIMIT 1`,
      [slug],
    )
    const r = rows[0]
    if (!r) return null
    return {
      slug: String(r.slug),
      name: String(r.name),
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
