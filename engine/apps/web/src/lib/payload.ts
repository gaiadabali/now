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
