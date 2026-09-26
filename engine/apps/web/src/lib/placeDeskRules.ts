/**
 * The place desk's pure rules: the queue score, what "ready to approve"
 * means, the merge audit entry, and which names look like duplicates.
 *
 * Next-free and database-free so `node --test` covers them
 * (test/placeDesk.test.ts). The data layer that feeds them is
 * `lib/placeDesk.ts`; the screens are `team-editor/place-desk/`.
 */

/**
 * The plan's §9.1 queue score, the same formula `now-places rank` uses
 * (engine/packages/place-catalogue/src/now_places/rank.py):
 * 3 × featured mentions + articles + 2 × active partnership + recency,
 * recency falling linearly from 1 (a mention published today) to 0 at five
 * years. Both suites pin the same worked examples.
 */
export const RECENCY_HORIZON_DAYS = 1825

export function recency(newest: Date | null, now: Date): number {
  if (!newest) return 0
  const ageDays = Math.max(0, (now.getTime() - newest.getTime()) / 86_400_000)
  return Math.max(0, 1 - ageDays / RECENCY_HORIZON_DAYS)
}

export function evidenceScore(featured: number, articles: number, partnered: boolean, newest: Date | null, now: Date): number {
  return 3 * featured + articles + (partnered ? 2 : 0) + recency(newest, now)
}

export type Ranked = { id: number; score: number; featured: number; articles: number }

/** Highest score first; ties by featured, articles, then the older id. */
export function compareRanked(a: Ranked, b: Ranked): number {
  return b.score - a.score || b.featured - a.featured || b.articles - a.articles || a.id - b.id
}

/**
 * Types a venue can be approved as. `editorial` and `unknown` are the
 * loader's placeholders ("not classified yet"), and `event` is not a venue;
 * approving a place under any of them would put an untyped row in front of
 * readers and into the rails, where competitor exclusion depends on the
 * type (plan §9.3 step 4).
 */
export const VENUE_TYPES = ['stay', 'eat', 'drink', 'wellness', 'do', 'shop'] as const

export type ApprovalCheck = { ok: true } | { ok: false; why: string }

export function approvalCheck(place: {
  status: string
  mergedInto: number | null
  type: string | null
  subtype: string | null
}): ApprovalCheck {
  if (place.mergedInto) return { ok: false, why: 'This place was merged into another. Approve that one instead.' }
  if (place.status === 'active') return { ok: false, why: 'Already approved.' }
  if (!place.type || !(VENUE_TYPES as readonly string[]).includes(place.type)) {
    return { ok: false, why: 'Say what kind of place it is first. Readers and the suggestion rails rely on it.' }
  }
  if (!place.subtype || place.subtype === 'city-guide') {
    return { ok: false, why: 'Choose the kind of place (for example Restaurant, Resort, Spa) first.' }
  }
  return { ok: true }
}

/**
 * One merge's audit entry on the surviving place's `aliases` -- the exact
 * shape `now-places merge` writes (merge.py), so `now-places unmerge`
 * reverses a desk merge the same way it reverses its own.
 */
export type AliasEntry = {
  name: string
  placeId: number
  mergedAt: string
  by: string
  score: number | null
  mentionIds: number[]
  repointedPlaceIds: number[]
  inheritedAliases: string[]
}

export function aliasNames(aliases: unknown): string[] {
  if (!Array.isArray(aliases)) return []
  const names: string[] = []
  for (const e of aliases) {
    if (typeof e === 'string') names.push(e)
    else if (e && typeof e === 'object' && typeof (e as AliasEntry).name === 'string') {
      names.push((e as AliasEntry).name)
      for (const n of (e as AliasEntry).inheritedAliases ?? []) if (typeof n === 'string') names.push(n)
    }
  }
  return names
}

export function mergeEntry(args: {
  loser: { id: number; name: string; aliases: unknown }
  mentionIds: number[]
  repointedPlaceIds: number[]
  by: string
  at: Date
}): AliasEntry {
  return {
    name: args.loser.name,
    placeId: args.loser.id,
    mergedAt: args.at.toISOString(),
    by: args.by,
    score: null,
    mentionIds: [...args.mentionIds].sort((a, b) => a - b),
    repointedPlaceIds: [...args.repointedPlaceIds].sort((a, b) => a - b),
    inheritedAliases: aliasNames(args.loser.aliases),
  }
}

/**
 * The word two duplicates are most likely to share: the first word of the
 * name that is not a generic venue word or the site's own name
 * (`now_place_extraction.normalize.blocking_key`, which the dedupe CLI
 * blocks on). "The Westin Resort Nusa Dua" -> "westin".
 */
const GENERIC = new Set([
  'the', 'a', 'an', 'and', 'at', 'of', 'by', 'in', 'on',
  'hotel', 'hotels', 'resort', 'resorts', 'restaurant', 'restaurants',
  'cafe', 'café', 'bar', 'bars', 'lounge', 'club', 'spa', 'villa', 'villas',
  'beach', 'rooftop', 'residence', 'residences', 'suites', 'suite',
  'boutique', 'gallery', 'museum', 'indonesia',
])

export function duplicateKey(name: string, siteWords: readonly string[]): string | null {
  const skip = new Set([...GENERIC, ...siteWords.map((w) => w.toLowerCase())])
  const tokens = name
    .normalize('NFKD')
    .replace(/\p{Mn}/gu, '')
    .toLowerCase()
    .replace(/[’‘'`]/g, '')
    .replace(/[^a-z0-9\s]/g, ' ')
    .split(/\s+/)
    .filter(Boolean)
  const core = tokens.filter((t) => !skip.has(t))
  const key = (core.length ? core : tokens)[0]
  return key && key.length >= 3 ? key : null
}

/**
 * Does a name point outside the site's region? The desk's version of
 * `now_places.region` (plan §1.1: Jakarta's table holds ~400 Bali venues).
 * It matches the location vocabulary's labels and slugs; the CLI also knows
 * the seed file's aliases ("Ungasan", "Petitenget"), so it flags a few more.
 * Either way the row is flagged for the editor, never moved.
 */
export type LocationTerm = { slug: string; label: string; parent: string | null }

export type RegionIndex = {
  needles: Array<{ re: RegExp; slug: string; depth: number }>
  regionOf: Map<string, string>
  labelOf: Map<string, string>
}

const REGION_STOPWORDS = new Set(['batu', 'kota', 'bukit', 'tim', 'solo'])

function normalizeName(text: string): string {
  return text
    .normalize('NFKD')
    .replace(/\p{Mn}/gu, '')
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function buildRegionIndex(terms: LocationTerm[]): RegionIndex {
  const bySlug = new Map(terms.map((t) => [t.slug, t]))
  const chain = (slug: string): string[] => {
    const out: string[] = []
    let cur = bySlug.get(slug)
    const seen = new Set<string>()
    while (cur && !seen.has(cur.slug)) {
      seen.add(cur.slug)
      out.push(cur.slug)
      cur = cur.parent ? bySlug.get(cur.parent) : undefined
    }
    return out
  }
  const regionOf = new Map<string, string>()
  const needles: RegionIndex['needles'] = []
  for (const t of terms) {
    const c = chain(t.slug)
    const depth = c.length - 1
    const root = c[c.length - 1]!
    regionOf.set(t.slug, root === 'indonesia' ? (c.length >= 2 ? c[c.length - 2]! : root) : root)
    if (depth === 0) continue
    for (const s of new Set([normalizeName(t.label), normalizeName(t.slug.replace(/-/g, ' '))])) {
      if (s.length < 4 || REGION_STOPWORDS.has(s)) continue
      // `s` is already [a-z0-9 ] only, so it needs no escaping.
      needles.push({ re: new RegExp(`(?<![a-z0-9])${s}(?![a-z0-9])`), slug: t.slug, depth })
    }
  }
  return { needles, regionOf, labelOf: new Map(terms.map((t) => [t.slug, t.label])) }
}

export type RegionVerdict = { outOfRegion: boolean; region: string | null; matched: string | null }

/**
 * Top-level regions directly under "indonesia" other than the city's own
 * all count as elsewhere, as does anything under "international".
 */
export function regionVerdict(name: string, index: RegionIndex, homeRegion: string): RegionVerdict {
  const hay = normalizeName(name)
  const hits = index.needles.filter((n) => n.re.test(hay))
  if (!hits.length) return { outOfRegion: false, region: null, matched: null }
  const regions = hits.map((h) => index.regionOf.get(h.slug) ?? null)
  if (regions.includes(homeRegion)) return { outOfRegion: false, region: homeRegion, matched: null }
  const best = hits.reduce((a, b) => (b.depth > a.depth ? b : a))
  return {
    outOfRegion: true,
    region: index.regionOf.get(best.slug) ?? null,
    matched: index.labelOf.get(best.slug) ?? best.slug,
  }
}
