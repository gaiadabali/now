import 'server-only'

import type { Where } from 'payload'

import { getRegistrySite } from '@/lib/queries'
import { decodeEntities } from '@/lib/html'
import { payloadClient } from '@/lib/payload'
import { getSiteConfig, railsFrom } from '@/lib/site'
import type { HomeRail } from '@/lib/site'

import { defaultBandOrder, DEPARTMENT_SECTIONS } from './paths'

/**
 * Server-side reads for the front-page editor. `actions.ts` is the write
 * half; this file never writes anything (mirrors the read/write split every
 * other admin area here uses — `platform/registry.ts` + `.../actions.ts`,
 * `lib/classification.ts` + its page's own inline queries).
 */

/** This process serves exactly one city (ARCHITECTURE.md §3.5) — the desk
 * only ever edits its own city's row, never another's. No literal city name
 * anywhere below; `SITE_SLUG` is the one and only branch. */
function requireSiteSlug(): string {
  const slug = process.env.SITE_SLUG
  if (!slug) throw new Error('SITE_SLUG is not set — see ARCHITECTURE.md §3.5.')
  return slug
}

export type FrontPageState = {
  siteSlug: string
  siteName: string
  /** What a reader gets today — `railsFrom(raw)`, or the scaffold order if
   * the row has never been governed. Never `null`: the editor always has
   * something to arrange. */
  rails: HomeRail[]
  /** Whether `rails` above came from a real, saved value (`true`) or is only
   * this screen's starting scaffold (`false`) — shown on screen so "Save"
   * reads as "start governing this" rather than implying nothing has
   * changed. */
  governed: boolean
  ttlSeconds: number
}

export async function getFrontPageState(): Promise<FrontPageState> {
  const slug = requireSiteSlug()
  const site = await getRegistrySite(slug)
  if (!site) {
    throw new Error(
      `No engine.sites row for "${slug}" — the registry seed (S1.3) has not run against this ` +
        'database. The front page cannot be governed until it has.',
    )
  }
  const validated = railsFrom(site.home_rails)
  return {
    siteSlug: site.slug,
    siteName: site.name,
    rails: validated ?? defaultBandOrder().map((key) => ({ key })),
    governed: validated !== null,
    // Same env var `lib/site.ts`'s `getSiteConfig()` reads, so this can
    // never quote a different number than the one actually governing reads.
    ttlSeconds: Number(process.env.SITE_CONFIG_TTL_MS ?? 30_000) / 1000,
  }
}

/**
 * The real, currently-governed nav — `Map<href without its leading slash,
 * label>` — so a `department:<section>` band reads as this site's actual
 * section name ("Resto & Bars section") rather than the internal slug
 * (`dining`). `getSiteConfig()` (`lib/site.ts`) is the SAME merged read the
 * masthead itself renders from (registry over the file), not a second guess
 * at what the nav says — if the console renamed a section five minutes ago,
 * this reads the new name.
 */
export async function getNavLabels(): Promise<Map<string, string>> {
  const { nav } = await getSiteConfig()
  return new Map(nav.map((item) => [item.href.replace(/^\//, ''), item.label]))
}

export type ArticleSummary = {
  id: number
  title: string
  slug: string | null
  status: string
  publishedAt: string | null
}

/**
 * Look up a set of article ids for display — pinned-story chips need a
 * headline to show, not just the number a console screen would be content
 * with. Missing ids (a pin whose article was deleted) are simply absent from
 * the result, same "skip, don't render a hole" rule `HomeRail.pins`'s own
 * doc comment states for the reader side.
 */
export async function resolveArticleSummaries(ids: number[]): Promise<Map<number, ArticleSummary>> {
  const unique = [...new Set(ids.filter((id) => Number.isInteger(id) && id > 0))]
  if (unique.length === 0) return new Map()
  const payload = await payloadClient()
  const { docs } = await payload.find({
    collection: 'articles',
    where: { id: { in: unique } },
    limit: unique.length,
    depth: 0,
    select: { title: true, slug: true, _status: true, publishedAt: true },
  })
  return new Map(
    docs.map((d) => [
      Number(d.id),
      {
        id: Number(d.id),
        title: decodeEntities(String(d.title ?? `Article ${d.id}`)),
        slug: typeof d.slug === 'string' ? d.slug : null,
        status: String(d._status ?? 'draft'),
        publishedAt: typeof d.publishedAt === 'string' ? d.publishedAt : null,
      },
    ]),
  )
}

const GUIDE_FORMATS = ['guide', 'city-guide']

/** Mirrors `lib/payload.ts`'s `TYPE_TO_SECTION`, inverted, for the reason
 * `paths.ts`'s `DEPARTMENT_SECTIONS` comment gives: an admin-only scaffold,
 * not a second definition the reader is bound by. */
const SECTION_TO_TYPES: Record<string, string[]> = {
  dining: ['eat', 'drink'],
  stay: ['stay'],
  wellness: ['wellness'],
  'things-to-do': ['do', 'shop'],
  events: ['event'],
  editorial: ['editorial'],
}

/**
 * "What fills the unpinned slots automatically" — an honest approximation,
 * not a re-implementation of the engine's own ranking. `getArticleRails` /
 * `getForYou` (`lib/recommend.ts`, WS1's contract) are the real thing for a
 * SINGLE article's rails; there is no equivalent home-page-band ranking
 * function to call yet (WS2 is building the home page itself in parallel),
 * so this shows the same recency ordering the site fell back to before
 * S6.3 wired the registry in, filtered where the band name makes a filter
 * obvious. Labelled as an approximation on screen, not presented as a
 * preview of the exact ranking a reader will see.
 */
export async function autoFillPreview(bandKey: string, excludeIds: number[], limit = 6): Promise<ArticleSummary[]> {
  const payload = await payloadClient()
  const where: Where = { _status: { equals: 'published' } }
  const and: Where[] = [where]

  if (bandKey.startsWith('department:')) {
    const section = bandKey.slice('department:'.length)
    const types = SECTION_TO_TYPES[section]
    if (types) and.push({ primaryType: { in: types } })
  } else if (bandKey === 'guides') {
    and.push({ format: { in: GUIDE_FORMATS } })
  }

  if (excludeIds.length > 0) and.push({ id: { not_in: excludeIds } })

  const { docs } = await payload.find({
    collection: 'articles',
    where: and.length > 1 ? { and } : where,
    sort: '-publishedAt',
    limit,
    depth: 0,
    select: { title: true, slug: true, _status: true, publishedAt: true },
  })

  return docs.map((d) => ({
    id: Number(d.id),
    title: decodeEntities(String(d.title ?? `Article ${d.id}`)),
    slug: typeof d.slug === 'string' ? d.slug : null,
    status: String(d._status ?? 'draft'),
    publishedAt: typeof d.publishedAt === 'string' ? d.publishedAt : null,
  }))
}

export { DEPARTMENT_SECTIONS }
