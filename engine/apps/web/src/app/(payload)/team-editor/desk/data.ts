import 'server-only'

import { cityPool, payloadClient } from '@/lib/payload'
import { platformConnectionString, query } from '@/lib/db'
import { canEditFrontPage, canReviewClassification, canViewRailAnalytics } from '@/lib/auth'
import { decodeEntities } from '@/lib/html'
import { railsAnalyticsHref } from '../platform/paths'
import type { StaffUser } from '@/lib/auth'

import {
  ARTICLE_CREATE,
  articlesFilteredHref,
  FRONT_PAGE_ROOT,
  MEDIA_CREATE,
  REVIEW_ROOT,
} from './paths'

/**
 * Everything the desk home needs, gathered in one place — same shape as
 * `platform/registry.ts` and `lib/classification.ts`: a page component reads
 * this, it does not run its own queries.
 *
 * REAL DATA ONLY (DESIGN-SYSTEM.md §5/§1's "invented counts... in shipped
 * code" rule, written for the reader site and just as true of the desk that
 * writes it). Every count below is a live query against this city's own
 * database, run fresh on every load — there is no cache here the way
 * `getSiteConfig()` has one, because a writer opening their desk expects to
 * see what just happened, not what happened up to 30 seconds ago.
 */

const PUBLISHED = { _status: { equals: 'published' } } as const

export type DeskUser = StaffUser & { name?: string }

export type Counted = { count: number; href: string | null }

export type DeskData = {
  greetingName: string
  isReviewer: boolean
  canEditFrontPage: boolean
  myDrafts: Counted & { note: string }
  scheduled: Counted
  reviewQueue: Counted | null
  problems: {
    noHero: Counted
    noStandfirst: Counted
    noType: Counted
    noArea: Counted & { unavailable?: boolean }
  }
  recentlyPublished: Array<{
    id: number
    title: string
    slug: string | null
    publishedAt: string | null
  }>
  quickActions: {
    write: string
    upload: string
    review: string | null
    frontPage: string | null
    /** Editor/admin only — the page otherwise had no way in but its URL. */
    suggestions: string | null
  }
}

/**
 * "My drafts" — exact, via `articles.createdBy`.
 *
 * Approved as a follow-up once the desk home shipped without a reliable
 * "is this yours": `author` is the public byline (`Authors.ts`'s own
 * header — "not to `users`"), so this used to match on name, best-effort.
 * `createdBy` (`stampCreatedBy` hook, set once on create) is a real link
 * now, and this counts against it directly — no guessing, no name matching.
 *
 * **Existing rows have nobody recorded.** The migration added the column
 * with no backfill — nothing recorded who started any of the 4,000+ rows
 * already in this archive before today, and there was no honest way to
 * guess it. `MY_DRAFTS_NOTE` says so on screen, in the reader's own words,
 * every time — not only when the count looks suspiciously low — because the
 * scope of what this counts is worth stating plainly rather than leaving a
 * writer to work out why an old draft they remember starting isn't here.
 */
const MY_DRAFTS_NOTE = 'Counts drafts you started here. Stories begun before today aren’t linked to anyone yet.'

/**
 * Published articles carrying the platform's `location` facet, straight from
 * `engine.entity_terms` — the same two-database read `areasWithCounts()`
 * (lib/payload.ts) and `lib/classification.ts` already do, for the same
 * reason: this is the classifier's real output, and it is NOT reachable
 * through any field on `articles` — `reviewQueueHooks.ts`'s own `FIELD_MAP`
 * comment says why ("articles have no subtype or area/location field").
 * `place-mentions` is a different, much sparser signal (a person linking a
 * span of text to a venue) and would under-count "has an area" badly if used
 * as a proxy here — this reads the real thing instead.
 *
 * Read-only, both connections, exactly like its precedents. Degrades to
 * `null` (not a thrown error, not a zero that could be misread as "every
 * story has an area") when either database is unreachable.
 */
async function locationTaggedArticleIds(): Promise<Set<number> | null> {
  const platformUrl = platformConnectionString()
  if (!platformUrl) return null
  try {
    const termRows = await query<{ id: string }>(
      `SELECT t.id::text AS id
         FROM engine.terms t
         JOIN engine.facets f ON f.id = t.facet_id
        WHERE f.key = 'location'`,
    )
    if (termRows.length === 0) return new Set()
    const termIds = termRows.map((r) => r.id)
    const { rows } = await cityPool().query<{ entity_id: string }>(
      `SELECT DISTINCT entity_id
         FROM engine.entity_terms
        WHERE entity_type = 'article' AND term_id = ANY($1::uuid[])`,
      [termIds],
    )
    return new Set(rows.map((r) => Number(r.entity_id)).filter(Number.isFinite))
  } catch (err) {
    console.error('[desk] could not read the location facet — "no area" will show as unavailable.', err)
    return null
  }
}

export async function getDeskData(user: DeskUser): Promise<DeskData> {
  const payload = await payloadClient()
  const reviewer = canReviewClassification(user)
  const editsFrontPage = canEditFrontPage(user)
  const nowIso = new Date().toISOString()

  const [
    myDraftsCount,
    scheduledCount,
    reviewQueueCount,
    noHeroCount,
    noStandfirstCount,
    noTypeCount,
    publishedIdRows,
    recent,
  ] = await Promise.all([
    payload.count({
      collection: 'articles',
      where: { and: [{ _status: { equals: 'draft' } }, { createdBy: { equals: user.id } }] },
    }),
    payload.count({
      collection: 'articles',
      where: { and: [{ _status: { equals: 'draft' } }, { publishedAt: { greater_than: nowIso } }] },
    }),
    reviewer
      ? payload.count({ collection: 'classification-reviews', where: { reviewState: { equals: 'pending' } } })
      : Promise.resolve(null),
    payload.count({ collection: 'articles', where: { and: [PUBLISHED, { heroMedia: { exists: false } }] } }),
    payload.count({
      collection: 'articles',
      where: { and: [PUBLISHED, { or: [{ dek: { exists: false } }, { dek: { equals: '' } }] }] },
    }),
    payload.count({ collection: 'articles', where: { and: [PUBLISHED, { primaryType: { exists: false } }] } }),
    payload.find({
      collection: 'articles',
      where: PUBLISHED,
      pagination: false,
      depth: 0,
      sort: '-publishedAt',
      select: { id: true },
    }),
    payload.find({
      collection: 'articles',
      where: PUBLISHED,
      sort: '-publishedAt',
      limit: 6,
      depth: 0,
      select: { title: true, slug: true, publishedAt: true },
    }),
  ])

  const locationTagged = await locationTaggedArticleIds()
  const publishedIds = publishedIdRows.docs.map((d) => Number(d.id)).filter(Number.isFinite)
  const missingAreaIds =
    locationTagged === null ? [] : publishedIds.filter((id) => !locationTagged.has(id))

  return {
    greetingName: user.name?.trim() || user.email,
    isReviewer: reviewer,
    canEditFrontPage: editsFrontPage,
    myDrafts: {
      note: MY_DRAFTS_NOTE,
      count: myDraftsCount.totalDocs,
      href: articlesFilteredHref({
        and: [{ _status: { equals: 'draft' } }, { createdBy: { equals: user.id } }],
      }),
    },
    scheduled: {
      count: scheduledCount.totalDocs,
      href: articlesFilteredHref({
        and: [{ _status: { equals: 'draft' } }, { publishedAt: { greater_than: nowIso } }],
      }),
    },
    reviewQueue: reviewer && reviewQueueCount ? { count: reviewQueueCount.totalDocs, href: REVIEW_ROOT } : null,
    problems: {
      noHero: {
        count: noHeroCount.totalDocs,
        href: articlesFilteredHref({ and: [PUBLISHED, { heroMedia: { exists: false } }] }),
      },
      noStandfirst: {
        count: noStandfirstCount.totalDocs,
        href: articlesFilteredHref({
          and: [PUBLISHED, { or: [{ dek: { exists: false } }, { dek: { equals: '' } }] }],
        }),
      },
      noType: {
        count: noTypeCount.totalDocs,
        href: articlesFilteredHref({ and: [PUBLISHED, { primaryType: { exists: false } }] }),
      },
      noArea:
        locationTagged === null
          ? { count: 0, href: null, unavailable: true }
          : {
              count: missingAreaIds.length,
              href:
                missingAreaIds.length > 0
                  ? articlesFilteredHref({ and: [PUBLISHED, { id: { in: missingAreaIds.slice(0, 200) } }] })
                  : null,
            },
    },
    recentlyPublished: recent.docs.map((d) => ({
      id: Number(d.id),
      title: decodeEntities(String(d.title ?? `Article ${d.id}`)),
      slug: typeof d.slug === 'string' ? d.slug : null,
      publishedAt: typeof d.publishedAt === 'string' ? d.publishedAt : null,
    })),
    quickActions: {
      write: ARTICLE_CREATE,
      upload: MEDIA_CREATE,
      review: reviewer ? REVIEW_ROOT : null,
      frontPage: editsFrontPage ? FRONT_PAGE_ROOT : null,
      suggestions: canViewRailAnalytics(user) ? railsAnalyticsHref() : null,
    },
  }
}
