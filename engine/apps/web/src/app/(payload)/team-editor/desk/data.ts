import 'server-only'

import { cityPool } from '@/lib/payload'
import { platformConnectionString, query } from '@/lib/db'
import { canEditFrontPage, canReviewClassification } from '@/lib/auth'
import type { StaffUser } from '@/lib/auth'
import { payloadClient } from '@/lib/payload'

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
  myDrafts: Counted & { matched: boolean }
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
  }
}

/**
 * "My drafts" needs to know which `authors` row (the public byline) belongs
 * to the signed-in CMS login. There is no such link in the schema —
 * `Authors.ts`'s own header says so plainly: "`articles.author` relates to
 * this collection, not to `users`." Adding `articles.createdBy` would fix
 * this properly; it is a schema change (a new column + a Payload migration
 * against two live-ish city databases while three other workstreams are
 * mid-flight against the same collection), which is the architect's call,
 * not this ticket's. Until then this MATCHES ON NAME, best-effort, and says
 * so on screen rather than pretending the match is exact — a wrong "yours"
 * on somebody else's unpublished draft would be a worse bug than an honest
 * "we can't tell yet".
 */
async function findAuthorIdsForUser(
  payload: Awaited<ReturnType<typeof payloadClient>>,
  user: DeskUser,
): Promise<number[]> {
  const name = user.name?.trim()
  if (!name) return []
  try {
    const { docs } = await payload.find({
      collection: 'authors',
      where: { name: { equals: name } },
      limit: 5,
      depth: 0,
      pagination: false,
    })
    return docs.map((d) => Number(d.id)).filter(Number.isFinite)
  } catch {
    return []
  }
}

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

  const authorIds = await findAuthorIdsForUser(payload, user)

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
    authorIds.length > 0
      ? payload.count({
          collection: 'articles',
          where: { and: [{ _status: { equals: 'draft' } }, { author: { in: authorIds } }] },
        })
      : Promise.resolve({ totalDocs: 0 }),
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
      matched: authorIds.length > 0,
      count: myDraftsCount.totalDocs,
      href:
        authorIds.length > 0
          ? articlesFilteredHref({ and: [{ _status: { equals: 'draft' } }, { author: { in: authorIds } }] })
          : null,
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
      title: String(d.title ?? `Article ${d.id}`),
      slug: typeof d.slug === 'string' ? d.slug : null,
      publishedAt: typeof d.publishedAt === 'string' ? d.publishedAt : null,
    })),
    quickActions: {
      write: ARTICLE_CREATE,
      upload: MEDIA_CREATE,
      review: reviewer ? REVIEW_ROOT : null,
      frontPage: editsFrontPage ? FRONT_PAGE_ROOT : null,
    },
  }
}
