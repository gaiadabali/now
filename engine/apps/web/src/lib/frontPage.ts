import 'server-only'

import {
  getByIds,
  getLatest,
  getSectionPage,
  type Article,
} from '@/lib/content'
import { areasWithCounts } from '@/lib/payload'
import { getForYou, type ArticleRail, type ReaderContext } from '@/lib/recommend'
import { getSiteConfig, type HomeRail, type SiteConfig } from '@/lib/site'

/**
 * The home page's own data assembly — one server module, so the page
 * component only renders what comes back (EDITION-2-PLAN §3: "the desk
 * writes them, the home page reads them").
 *
 * Two rules this file exists to enforce, that a page component assembling
 * its own queries kept getting wrong before:
 *
 * 1. **`HomeRail.pins` lead a band, in order, then its automatic fill** — and
 *    a pin that no longer resolves to a published article (unpublished,
 *    deleted, mistyped id) is skipped rather than rendered as a hole or a
 *    crash. `getByIds` (lib/content.ts) already applies the `PUBLISHED` gate.
 * 2. **Every story appears once per page.** The previous home page queried
 *    each band independently, which is exactly how the Hotels band ended up
 *    repeating the cover story (IHG/Kimpton) as its own lead — both bands
 *    asked "what's newest" and got the same answer. `used` is threaded
 *    through every band in rendering order and nothing after the first band
 *    to claim a story may claim it again.
 */

export type FrontLeadItem = Article
export type FrontBand =
  | { key: 'lead'; kind: 'lead'; hero: FrontLeadItem; secondaries: Article[]; ticker: Article[] }
  | { key: 'edit'; kind: 'edit'; kicker: string; title: string; items: Article[] }
  | { key: 'for-you'; kind: 'for-you'; rail: ArticleRail }
  | { key: `department:${string}`; kind: 'department'; section: string; kicker: string; title: string; moreHref: string; lead: Article; side: Article[] }
  | { key: 'guides'; kind: 'guides'; kicker: string; title: string; items: Article[] }
  | { key: 'latest'; kind: 'latest'; kicker: string; title: string; items: Article[] }
  | { key: 'explore'; kind: 'explore'; kicker: string; title: string; areas: Array<{ slug: string; label: string; count: number }> }

export type FrontPage = {
  site: SiteConfig
  bands: FrontBand[]
}

/** No `sites.home_rails` row: the shape this page has always had, in order.
 *  `for-you` sits right after `edit` so the day WS1's engine starts returning
 *  a real personalised rail, it appears with no further change here — the
 *  contract already says a null `getForYou` renders nothing. */
const DEFAULT_ORDER: HomeRail[] = [
  { key: 'lead' },
  { key: 'edit' },
  { key: 'for-you' },
  { key: 'department:stay' },
  { key: 'guides' },
  { key: 'latest' },
  { key: 'explore' },
]

const KNOWN_KEYS = new Set(['lead', 'edit', 'for-you', 'guides', 'latest', 'explore'])
function isKnownKey(key: string): boolean {
  return KNOWN_KEYS.has(key) || key.startsWith('department:')
}

/** Pins first (in the order given, published only, deduped against every
 *  earlier band), then `pool` fills the rest. `pool` should already be
 *  over-fetched by the caller — comfortably more than `limit` — because
 *  dedupe removes an unpredictable number before this ever sees it. */
function pinsThenFill(pins: number[] | undefined, pinned: Article[], pool: Article[], used: Set<number>, limit: number): Article[] {
  const keptPins = pinned.filter((a) => !used.has(a.id)).slice(0, limit)
  keptPins.forEach((a) => used.add(a.id))
  const remaining = limit - keptPins.length
  if (remaining <= 0) return keptPins
  const fill = pool.filter((a) => !used.has(a.id)).slice(0, remaining)
  fill.forEach((a) => used.add(a.id))
  return [...keptPins, ...fill]
}

/** Overfetch factor for a band's automatic fill: enough slack that a page
 *  with several curated pins and several earlier bands still has real
 *  content left to fill with, without a second round-trip. */
const SLACK = 10

export async function getFrontPage(reader: ReaderContext = {}): Promise<FrontPage> {
  const site = await getSiteConfig()
  const order = site.homeRails?.filter((r) => isKnownKey(r.key)) ?? DEFAULT_ORDER
  const used = new Set<number>()
  const bands: FrontBand[] = []

  for (const rail of order) {
    if (rail.key === 'lead') {
      // hero + 3 secondaries by default — the brief's own "3-4", and 3 is
      // what keeps the package's measured height inside the 1440×900 fold
      // budget alongside the hero's fixed-height media box (see
      // `.frontlead__secondaries` in magazine.css for the measurement).
      const limit = rail.limit ?? 4
      const pins = rail.pins ?? []
      const pinned = await getByIds(pins)
      const pool = await getLatest(limit + used.size + SLACK)
      const picked = pinsThenFill(pins, pinned, pool, used, limit)
      const [hero, ...secondaries] = picked
      if (!hero) continue // nothing published at all (fresh city) — page.tsx handles that state
      // The above-the-fold "Latest" strip: real, timestamped, and never one
      // of the stories the lead package just told. Not the deep `latest`
      // band further down the page — that one is the full paginated index.
      const tickerPool = await getLatest(4 + used.size + SLACK)
      const ticker = tickerPool.filter((a) => !used.has(a.id)).slice(0, 4)
      ticker.forEach((a) => used.add(a.id))
      bands.push({ key: 'lead', kind: 'lead', hero, secondaries, ticker })
      continue
    }

    if (rail.key === 'edit') {
      const limit = rail.limit ?? 4
      const pins = rail.pins ?? []
      const pinned = await getByIds(pins)
      const pool = await getLatest(limit + used.size + SLACK)
      const items = pinsThenFill(pins, pinned, pool, used, limit)
      if (items.length === 0) continue
      bands.push({ key: 'edit', kind: 'edit', kicker: rail.note ?? 'Chosen this week', title: rail.label ?? 'The Edit', items })
      continue
    }

    if (rail.key === 'for-you') {
      const forYou = await getForYou(reader, rail.limit ?? 6)
      if (!forYou || forYou.items.length === 0) continue
      bands.push({ key: 'for-you', kind: 'for-you', rail: forYou })
      continue
    }

    if (rail.key === 'guides') {
      const limit = rail.limit ?? 5
      const pins = rail.pins ?? []
      const pinned = await getByIds(pins)
      const page = await getSectionPage('guides', { limit: limit + used.size + SLACK })
      const items = pinsThenFill(pins, pinned, page.items, used, limit)
      if (items.length === 0) continue
      bands.push({
        key: 'guides',
        kind: 'guides',
        kicker: rail.note ?? `${page.total} GUIDES`,
        title: rail.label ?? 'The Guides',
        items,
      })
      continue
    }

    if (rail.key === 'latest') {
      const limit = rail.limit ?? 12
      const pool = await getLatest(limit + used.size + SLACK)
      const items = pool.filter((a) => !used.has(a.id)).slice(0, limit)
      items.forEach((a) => used.add(a.id))
      if (items.length === 0) continue
      bands.push({ key: 'latest', kind: 'latest', kicker: rail.note ?? 'Newest first', title: rail.label ?? 'Latest', items })
      continue
    }

    if (rail.key === 'explore') {
      const areas = (await areasWithCounts()).slice(0, rail.limit ?? 12)
      if (areas.length === 0) continue
      bands.push({
        key: 'explore',
        kind: 'explore',
        kicker: rail.note ?? `${areas.length} NEIGHBOURHOODS`,
        title: rail.label ?? 'Explore',
        areas,
      })
      continue
    }

    if (rail.key.startsWith('department:')) {
      const section = rail.key.slice('department:'.length)
      const limit = rail.limit ?? 4 // one lead + up to 3 side items
      const pins = rail.pins ?? []
      const pinned = await getByIds(pins)
      const page = await getSectionPage(section, { limit: limit + used.size + SLACK })
      const items = pinsThenFill(pins, pinned, page.items, used, limit)
      const [lead, ...side] = items
      if (!lead) continue
      bands.push({
        key: rail.key as `department:${string}`,
        kind: 'department',
        section,
        kicker: rail.note ?? `${page.total} STORIES`,
        title: rail.label ?? sectionTitle(section),
        moreHref: `/${section}`,
        lead,
        side,
      })
      continue
    }
  }

  return { site, bands }
}

/** The one department the built-in order names by section slug rather than
 *  by an editor-supplied label, so it needs its own title casing. Anything
 *  the console pins to a different section falls back to the same
 *  `sectionLabel` humanisation `[slug]/page.tsx` uses for a section index. */
function sectionTitle(section: string): string {
  if (section === 'stay') return 'Hotels'
  return section
    .split('-')
    .map((w) => w[0]?.toUpperCase() + w.slice(1))
    .join(' ')
}
