import 'server-only'

import { db as platformDb } from '@/lib/db'
import { decodeEntities } from '@/lib/html'
import { cityPool } from '@/lib/payload'
import { classifyPlaceName, nonVenuePhraseSet, type JunkVerdict } from '@/lib/placeJunk'
import {
  buildRegionIndex,
  compareRanked,
  duplicateKey,
  evidenceScore,
  regionVerdict,
  type LocationTerm,
  type RegionIndex,
  type RegionVerdict,
} from '@/lib/placeDeskRules'

/**
 * Reads for the place desk (plan §9, P1.6).
 *
 * Same split as the classification desk (`lib/review.ts`): reads are plain
 * SQL on the city pool, because the queue is an aggregate Payload's list
 * view cannot express (evidence per place, ranked); every WRITE goes through
 * the Payload Local API in `team-editor/place-desk/actions.ts`, so the
 * `places` hooks run, a version is recorded, and the actor is stamped.
 *
 * The queue is every `pending_review` place that has not been merged away,
 * in the plan's §9.1 order (`placeDeskRules.evidenceScore`). Each row
 * carries the same junk verdict `now-places triage` reports (`placeJunk.ts`)
 * and a region check, so the desk can say "looks like junk" or "names
 * another region" before an editor reads a word.
 */

// ------------------------------------------------------------ vocabulary

let phrasesCache: { at: number; set: Set<string> } | null = null

/** The extractor's noise list: this city's `enum_places_area_term` values
 * plus its supplementary phrases (`placeJunk.nonVenuePhraseSet`). */
async function nonVenuePhrases(): Promise<Set<string>> {
  if (phrasesCache && Date.now() - phrasesCache.at < 10 * 60_000) return phrasesCache.set
  let values: string[] = []
  try {
    const { rows } = await cityPool().query(`SELECT unnest(enum_range(NULL::enum_places_area_term))::text AS v`)
    values = rows.map((r) => String(r.v))
  } catch {
    values = []
  }
  phrasesCache = { at: Date.now(), set: nonVenuePhraseSet(values) }
  return phrasesCache.set
}

let locationCache: { at: number; terms: LocationTerm[]; index: RegionIndex } | null = null

async function locationTerms(): Promise<{ terms: LocationTerm[]; index: RegionIndex }> {
  if (locationCache && Date.now() - locationCache.at < 10 * 60_000) return locationCache
  let terms: LocationTerm[] = []
  try {
    const { rows } = await platformDb().query(
      `SELECT t.slug, t.label, p.slug AS parent
         FROM engine.terms t
         JOIN engine.facets f ON f.id = t.facet_id
         LEFT JOIN engine.terms p ON p.id = t.parent_id
        WHERE f.key = 'location'
        ORDER BY t.label`,
    )
    terms = rows.map((r) => ({ slug: String(r.slug), label: String(r.label), parent: r.parent ? String(r.parent) : null }))
  } catch {
    terms = []
  }
  locationCache = { at: Date.now(), terms, index: buildRegionIndex(terms) }
  return locationCache
}

export type SubtypeGroup = { type: string; label: string; subtypes: Array<{ slug: string; label: string }> }

/** "What kind of place is it?" -- subtypes grouped under their venue type. */
export async function subtypeOptions(): Promise<SubtypeGroup[]> {
  try {
    const { rows } = await platformDb().query(
      `SELECT t.slug, t.label, p.slug AS type, p.label AS type_label
         FROM engine.terms t
         JOIN engine.facets f ON f.id = t.facet_id
         JOIN engine.terms p ON p.id = t.parent_id
        WHERE f.key = 'subtype' AND p.slug IN ('stay', 'eat', 'drink', 'wellness', 'do', 'shop')
        ORDER BY p.label, t.label`,
    )
    const groups = new Map<string, SubtypeGroup>()
    for (const r of rows) {
      const type = String(r.type)
      if (!groups.has(type)) groups.set(type, { type, label: String(r.type_label), subtypes: [] })
      groups.get(type)!.subtypes.push({ slug: String(r.slug), label: String(r.label) })
    }
    return [...groups.values()]
  } catch {
    return []
  }
}

export type AreaOption = { slug: string; label: string; parentLabel: string | null }

/** Areas in this city first (the site's own region subtree), then the rest. */
export async function areaOptions(homeRegion: string): Promise<{ home: AreaOption[]; elsewhere: AreaOption[] }> {
  const { terms, index } = await locationTerms()
  const labelOf = new Map(terms.map((t) => [t.slug, t.label]))
  const home: AreaOption[] = []
  const elsewhere: AreaOption[] = []
  for (const t of terms) {
    if (!t.parent) continue
    const option = { slug: t.slug, label: t.label, parentLabel: t.parent ? labelOf.get(t.parent) ?? null : null }
    if (index.regionOf.get(t.slug) === homeRegion) home.push(option)
    else elsewhere.push(option)
  }
  return { home, elsewhere }
}

// ------------------------------------------------------------ partnerships

async function partnered(siteSlug: string): Promise<{ places: Set<string>; orgs: Set<string>; read: boolean }> {
  const client = await platformDb()
    .connect()
    .catch(() => null)
  if (!client) return { places: new Set(), orgs: new Set(), read: false }
  try {
    await client.query('BEGIN')
    const site = await client.query(`SELECT id FROM engine.sites WHERE slug = $1`, [siteSlug])
    const siteId = site.rows[0]?.id
    if (!siteId) {
      await client.query('ROLLBACK')
      return { places: new Set(), orgs: new Set(), read: true }
    }
    // engine.partnerships is RLS-scoped by app.site_id (migration 0017).
    await client.query(`SELECT set_config('app.site_id', $1, true)`, [String(siteId)])
    const { rows } = await client.query(
      `SELECT place_id, org_id::text AS org_id FROM engine.partnerships
        WHERE site_id = $1 AND status = 'active' AND (ends_at IS NULL OR ends_at > now())`,
      [siteId],
    )
    await client.query('ROLLBACK')
    return {
      places: new Set(rows.filter((r) => r.place_id).map((r) => String(r.place_id))),
      orgs: new Set(rows.filter((r) => r.org_id).map((r) => String(r.org_id))),
      read: true,
    }
  } catch {
    await client.query('ROLLBACK').catch(() => {})
    return { places: new Set(), orgs: new Set(), read: false }
  } finally {
    client.release()
  }
}

// ------------------------------------------------------------------ queue

const verdictMemo = new Map<string, JunkVerdict>()
const regionMemo = new Map<string, RegionVerdict>()

function memo<T>(map: Map<string, T>, key: string, make: () => T): T {
  const hit = map.get(key)
  if (hit !== undefined) return hit
  const value = make()
  if (map.size > 50_000) map.clear()
  map.set(key, value)
  return value
}

export type QueueRow = {
  id: number
  name: string
  slug: string
  status: string
  type: string | null
  subtype: string | null
  area: string | null
  reviewedBy: number | null
  featured: number
  articles: number
  mentions: number
  newest: Date | null
  partnered: boolean
  score: number
  rank: number
  junk: JunkVerdict
  region: RegionVerdict
}

export type Queue = { rows: QueueRow[]; partnershipRead: boolean }

const EVIDENCE_JOIN = `
  LEFT JOIN (
    SELECT pm.place_id,
           count(*) FILTER (WHERE pm.role = 'featured')::int AS featured,
           count(*)::int AS mentions,
           count(DISTINCT pm.article_id)::int AS articles,
           max(a.published_at) AS newest
      FROM public.place_mentions pm
      LEFT JOIN public.articles a ON a.id = pm.article_id
     GROUP BY pm.place_id
  ) m ON m.place_id = p.id`

/** Every pending, unmerged place, ranked. */
export async function loadQueue(siteSlug: string): Promise<Queue> {
  const [phrases, { index }, partners, result] = await Promise.all([
    nonVenuePhrases(),
    locationTerms(),
    partnered(siteSlug),
    cityPool().query(
      `SELECT p.id, p.name, p.slug, p.status::text AS status, p.type::text AS type, p.subtype::text AS subtype,
              p.area_term::text AS area, p.org_id, p.reviewed_by_id,
              coalesce(m.featured, 0) AS featured, coalesce(m.articles, 0) AS articles,
              coalesce(m.mentions, 0) AS mentions, m.newest
         FROM public.places p ${EVIDENCE_JOIN}
        WHERE p.merged_into_id IS NULL AND p.status = 'pending_review'`,
    ),
  ])
  const now = new Date()
  const rows: QueueRow[] = result.rows.map((r) => {
    const name = String(r.name)
    const isPartnered = partners.places.has(String(r.id)) || (r.org_id ? partners.orgs.has(String(r.org_id)) : false)
    const newest = r.newest ? new Date(r.newest) : null
    return {
      id: Number(r.id),
      name: decodeEntities(name),
      slug: String(r.slug),
      status: String(r.status),
      type: r.type ? String(r.type) : null,
      subtype: r.subtype ? String(r.subtype) : null,
      area: r.area ? String(r.area) : null,
      reviewedBy: r.reviewed_by_id === null ? null : Number(r.reviewed_by_id),
      featured: Number(r.featured),
      articles: Number(r.articles),
      mentions: Number(r.mentions),
      newest,
      partnered: isPartnered,
      score: evidenceScore(Number(r.featured), Number(r.articles), isPartnered, newest, now),
      rank: 0,
      // Classified on the raw name, exactly as the CLI sees it.
      junk: memo(verdictMemo, name, () => classifyPlaceName(name, phrases)),
      region: memo(regionMemo, `${siteSlug}\u0000${name}`, () => regionVerdict(name, index, siteSlug)),
    }
  })
  // Junk-shaped rows no editor has kept are not part of the curation order;
  // they sit in their own "looks like junk" list for bulk confirmation.
  const ranked = rows.filter((r) => !(r.junk.tier === 'junk' && r.reviewedBy === null)).sort(compareRanked)
  ranked.forEach((r, i) => (r.rank = i + 1))
  return { rows, partnershipRead: partners.read }
}

export type QueueFilter = 'queue' | 'junk' | 'suspect' | 'region' | 'kept'

export function filterQueue(rows: QueueRow[], filter: QueueFilter): QueueRow[] {
  const unkeptJunk = (r: QueueRow) => r.junk.tier === 'junk' && r.reviewedBy === null
  const byRank = (a: QueueRow, b: QueueRow) => a.rank - b.rank
  switch (filter) {
    case 'junk':
      return rows.filter(unkeptJunk).sort((a, b) => compareRanked(a, b))
    case 'suspect':
      return rows.filter((r) => !unkeptJunk(r) && r.junk.tier === 'suspect').sort(byRank)
    case 'region':
      return rows.filter((r) => !unkeptJunk(r) && r.region.outOfRegion).sort(byRank)
    case 'kept':
      return rows.filter((r) => r.reviewedBy !== null).sort(byRank)
    default:
      return rows.filter((r) => !unkeptJunk(r)).sort(byRank)
  }
}

// ----------------------------------------------------------------- counts

export type DeskCounts = {
  waiting: number
  approved: number
  junk: number
  merged: number
  decidedToday: number
  decidedTodayByMe: number
  decidedThisWeek: number
}

/**
 * The throughput counter. A "decision" is a place whose newest version
 * carries a reviewer and was written today (in the site's timezone) --
 * approvals, junk, merges, type and area calls, "keep". Counted from
 * Payload's own version table, so it reflects what was actually saved.
 */
export async function deskCounts(userId: number, timezone: string): Promise<DeskCounts> {
  try {
    const { rows } = await cityPool().query(
      `WITH day AS (SELECT (date_trunc('day', now() AT TIME ZONE $2) AT TIME ZONE $2) AS start)
       SELECT
         (SELECT count(*)::int FROM public.places WHERE status = 'pending_review' AND merged_into_id IS NULL) AS waiting,
         (SELECT count(*)::int FROM public.places WHERE status = 'active' AND merged_into_id IS NULL) AS approved,
         (SELECT count(*)::int FROM public.places WHERE status = 'junk') AS junk,
         (SELECT count(*)::int FROM public.places WHERE merged_into_id IS NOT NULL) AS merged,
         (SELECT count(DISTINCT parent_id)::int FROM public._places_v, day
           WHERE version_reviewed_by_id IS NOT NULL AND created_at >= day.start) AS decided_today,
         (SELECT count(DISTINCT parent_id)::int FROM public._places_v, day
           WHERE version_reviewed_by_id = $1 AND created_at >= day.start) AS decided_today_by_me,
         (SELECT count(DISTINCT parent_id)::int FROM public._places_v, day
           WHERE version_reviewed_by_id IS NOT NULL AND created_at >= day.start - interval '6 days') AS decided_week`,
      [userId, timezone],
    )
    const r = rows[0] ?? {}
    return {
      waiting: Number(r.waiting ?? 0),
      approved: Number(r.approved ?? 0),
      junk: Number(r.junk ?? 0),
      merged: Number(r.merged ?? 0),
      decidedToday: Number(r.decided_today ?? 0),
      decidedTodayByMe: Number(r.decided_today_by_me ?? 0),
      decidedThisWeek: Number(r.decided_week ?? 0),
    }
  } catch {
    return { waiting: 0, approved: 0, junk: 0, merged: 0, decidedToday: 0, decidedTodayByMe: 0, decidedThisWeek: 0 }
  }
}

// ----------------------------------------------------------------- detail

export type DeskPlace = {
  id: number
  name: string
  slug: string
  status: string
  source: string | null
  type: string | null
  subtype: string | null
  area: string | null
  address: string | null
  lat: number | null
  lng: number | null
  googlePlaceId: string | null
  geoSource: string | null
  geoConfidence: number | null
  businessStatus: string | null
  regionOk: boolean | null
  externalTypes: unknown
  orgId: string | null
  mergedInto: number | null
  mergedIntoName: string | null
  aliases: unknown
  verifiedAt: string | null
  reviewedByEmail: string | null
  updatedAt: string | null
  featured: number
  articles: number
  mentions: number
  newest: Date | null
}

export async function deskPlace(id: number): Promise<DeskPlace | null> {
  const { rows } = await cityPool().query(
    `SELECT p.id, p.name, p.slug, p.status::text AS status, p.source::text AS source, p.type::text AS type,
            p.subtype::text AS subtype, p.area_term::text AS area, p.address, p.lat, p.lng, p.google_place_id,
            p.geo_source::text AS geo_source, p.geo_confidence, p.business_status::text AS business_status,
            p.region_ok, p.external_types, p.org_id, p.merged_into_id, mi.name AS merged_into_name, p.aliases,
            p.verified_at, u.email AS reviewed_by_email, p.updated_at,
            coalesce(m.featured, 0) AS featured, coalesce(m.articles, 0) AS articles,
            coalesce(m.mentions, 0) AS mentions, m.newest
       FROM public.places p ${EVIDENCE_JOIN}
       LEFT JOIN public.places mi ON mi.id = p.merged_into_id
       LEFT JOIN public.users u ON u.id = p.reviewed_by_id
      WHERE p.id = $1`,
    [id],
  )
  const r = rows[0]
  if (!r) return null
  const num = (v: unknown) => (v === null || v === undefined ? null : Number(v))
  return {
    id: Number(r.id),
    name: decodeEntities(String(r.name)),
    slug: String(r.slug),
    status: String(r.status),
    source: r.source ?? null,
    type: r.type ?? null,
    subtype: r.subtype ?? null,
    area: r.area ?? null,
    address: r.address ? decodeEntities(String(r.address)) : null,
    lat: num(r.lat),
    lng: num(r.lng),
    googlePlaceId: r.google_place_id ?? null,
    geoSource: r.geo_source ?? null,
    geoConfidence: num(r.geo_confidence),
    businessStatus: r.business_status ?? null,
    regionOk: r.region_ok ?? null,
    externalTypes: r.external_types ?? null,
    orgId: r.org_id ?? null,
    mergedInto: num(r.merged_into_id),
    mergedIntoName: r.merged_into_name ? decodeEntities(String(r.merged_into_name)) : null,
    aliases: r.aliases ?? null,
    verifiedAt: r.verified_at ? new Date(r.verified_at).toISOString() : null,
    reviewedByEmail: r.reviewed_by_email ?? null,
    updatedAt: r.updated_at ? new Date(r.updated_at).toISOString() : null,
    featured: Number(r.featured),
    articles: Number(r.articles),
    mentions: Number(r.mentions),
    newest: r.newest ? new Date(r.newest) : null,
  }
}

export type DeskMention = {
  id: number
  role: string
  surface: string
  articleId: number
  title: string
  slug: string | null
  publishedAt: Date | null
}

export const MENTION_LIMIT = 30

export async function deskMentions(placeId: number): Promise<DeskMention[]> {
  const { rows } = await cityPool().query(
    `SELECT pm.id, pm.role::text AS role, pm.surface_text, a.id AS article_id, a.title, a.slug, a.published_at
       FROM public.place_mentions pm
       JOIN public.articles a ON a.id = pm.article_id
      WHERE pm.place_id = $1
      ORDER BY (pm.role = 'featured') DESC, a.published_at DESC NULLS LAST, pm.id
      LIMIT ${MENTION_LIMIT}`,
    [placeId],
  )
  return rows.map((r) => ({
    id: Number(r.id),
    role: String(r.role),
    surface: decodeEntities(String(r.surface_text)),
    articleId: Number(r.article_id),
    title: decodeEntities(String(r.title ?? 'Untitled')),
    slug: r.slug ? String(r.slug) : null,
    publishedAt: r.published_at ? new Date(r.published_at) : null,
  }))
}

export type DuplicateCandidate = { id: number; name: string; status: string; featured: number; articles: number }

/**
 * Places that share this one's most distinctive word -- the same blocking
 * the dedupe CLI uses -- for the editor to judge. Scored pairs from
 * `now-places dedupe` live in its review-queue file; this list is the
 * desk's own, always current.
 */
export async function duplicateCandidates(place: { id: number; name: string }, siteWords: string[]): Promise<DuplicateCandidate[]> {
  const key = duplicateKey(place.name, siteWords)
  if (!key) return []
  const { rows } = await cityPool().query(
    `SELECT p.id, p.name, p.status::text AS status, coalesce(m.featured, 0) AS featured, coalesce(m.articles, 0) AS articles
       FROM public.places p ${EVIDENCE_JOIN}
      WHERE p.id <> $1 AND p.merged_into_id IS NULL AND p.status IN ('pending_review', 'active')
        AND lower(p.name) ~ $2
      ORDER BY coalesce(m.featured, 0) DESC, coalesce(m.articles, 0) DESC, p.id
      LIMIT 6`,
    [place.id, `(^|[^a-z0-9])${key}([^a-z0-9]|$)`],
  )
  return rows.map((r) => ({
    id: Number(r.id),
    name: decodeEntities(String(r.name)),
    status: String(r.status),
    featured: Number(r.featured),
    articles: Number(r.articles),
  }))
}

/** The junk verdict and region check for one place, as the queue shows them. */
export async function verdictsFor(name: string, siteSlug: string): Promise<{ junk: JunkVerdict; region: RegionVerdict }> {
  const [phrases, { index }] = await Promise.all([nonVenuePhrases(), locationTerms()])
  return {
    junk: memo(verdictMemo, name, () => classifyPlaceName(name, phrases)),
    region: memo(regionMemo, `${siteSlug}\u0000${name}`, () => regionVerdict(name, index, siteSlug)),
  }
}

/** Re-checked on the server before a bulk junk write: never trust the form. */
export async function stillJunkCandidates(ids: number[]): Promise<number[]> {
  if (!ids.length) return []
  const phrases = await nonVenuePhrases()
  const { rows } = await cityPool().query(
    `SELECT id, name FROM public.places
      WHERE id = ANY($1::int[]) AND status = 'pending_review' AND merged_into_id IS NULL AND reviewed_by_id IS NULL`,
    [ids],
  )
  return rows
    .filter((r) => memo(verdictMemo, String(r.name), () => classifyPlaceName(String(r.name), phrases)).tier === 'junk')
    .map((r) => Number(r.id))
}
