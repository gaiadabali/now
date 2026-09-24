/**
 * `GET /api/article-checklist/:id?heroMediaId=123` — the two facts the
 * "Ready to publish" sidebar (`packages/cms/src/fields/PublishChecklist.tsx`)
 * cannot get from the edit form's own state, and why each needs its own
 * round trip:
 *
 *   - **the hero image's alt text.** The Articles edit form only ever holds
 *     `heroMedia`'s id, not the related `media` document, so the alt text
 *     Media requires (`Media.ts`) is not in the form's own state to read.
 *   - **whether this article carries the platform's `location` facet.**
 *     `reviewQueueHooks.ts`'s own `FIELD_MAP` comment says why there is no
 *     field on `articles` to read this off directly: "articles have no
 *     subtype or area/location field" — it lives in `engine.entity_terms`,
 *     which `packages/cms` must never touch (ARCHITECTURE.md §1 principle
 *     2). This app already reads that exact table for the same reason
 *     (`lib/payload.ts`'s `areasWithCounts`, `lib/classification.ts`), and a
 *     literal route here — same trick `api/staff-login/route.ts` already
 *     uses — reaches it for a single article on demand rather than baking a
 *     second engine-reading path into `packages/cms`.
 *
 * A LITERAL route beside Payload's own `api/[...slug]` catch-all, which Next
 * resolves first at the same segment depth — exactly the mechanism
 * `api/staff-login/route.ts` already relies on, used here on purpose rather
 * than found by accident the way `(payload)/team-editor/**` was before S3.1.
 *
 * Staff-gated: not sensitive data, but every read in this app answers for
 * itself rather than trusting a caller (`lib/auth.ts`'s own running theme).
 */
import { headers as nextHeaders } from 'next/headers'
import { NextResponse } from 'next/server'

import { cityPool, payloadClient } from '@/lib/payload'
import { platformConnectionString, query } from '@/lib/db'

export async function GET(request: Request, context: { params: Promise<{ id: string }> }) {
  const payload = await payloadClient()
  const { user } = await payload.auth({ headers: await nextHeaders() })
  if (!user) return NextResponse.json({ error: 'Not signed in.' }, { status: 401 })

  const { id } = await context.params
  const articleId = Number(id)
  if (!Number.isFinite(articleId)) return NextResponse.json({ error: 'Bad article id.' }, { status: 400 })

  const { searchParams } = new URL(request.url)
  const heroMediaId = Number(searchParams.get('heroMediaId'))

  const [hero, hasArea] = await Promise.all([
    Number.isFinite(heroMediaId) && heroMediaId > 0 ? lookupHero(payload, heroMediaId) : Promise.resolve(null),
    lookupHasArea(articleId),
  ])

  return NextResponse.json({ heroAlt: hero?.alt ?? null, heroUrl: hero?.url ?? null, hasArea })
}

async function lookupHero(
  payload: Awaited<ReturnType<typeof payloadClient>>,
  mediaId: number,
): Promise<{ alt: string | null; url: string | null } | null> {
  try {
    const doc = await payload.findByID({ collection: 'media', id: mediaId, depth: 0 })
    return {
      alt: typeof doc?.alt === 'string' && doc.alt.trim() !== '' ? doc.alt : null,
      url: typeof doc?.url === 'string' ? doc.url : null,
    }
  } catch {
    return null
  }
}

/** `null` means "could not tell", not "no" — the checklist shows this
 * distinctly (see `PublishChecklist.tsx`) rather than reporting a false
 * negative because a database was briefly unreachable. */
async function lookupHasArea(articleId: number): Promise<boolean | null> {
  if (!platformConnectionString()) return null
  try {
    const termRows = await query<{ id: string }>(
      `SELECT t.id::text AS id
         FROM engine.terms t
         JOIN engine.facets f ON f.id = t.facet_id
        WHERE f.key = 'location'`,
    )
    if (termRows.length === 0) return false
    const { rows } = await cityPool().query<{ exists: boolean }>(
      `SELECT EXISTS (
         SELECT 1 FROM engine.entity_terms
          WHERE entity_type = 'article' AND entity_id = $1 AND term_id = ANY($2::uuid[])
       ) AS exists`,
      [articleId, termRows.map((r) => r.id)],
    )
    return rows[0]?.exists ?? false
  } catch {
    return null
  }
}
