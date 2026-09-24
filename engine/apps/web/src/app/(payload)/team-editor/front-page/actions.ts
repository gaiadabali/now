'use server'

import { revalidatePath } from 'next/cache'

import { requireFrontPageEditor } from '@/lib/auth'
import { payloadClient } from '@/lib/payload'
import { getRegistrySite, updateSiteHomeRails } from '@/lib/queries'
import { railsFrom } from '@/lib/site'
import type { HomeRail } from '@/lib/site'

import { autoFillPreview } from './data'
import type { ArticleSummary } from './data'
import { FRONT_PAGE_ROOT } from './paths'

/**
 * The write half of the front-page editor.
 *
 * **Does not call `platform/sites/[slug]/actions.ts`'s `saveHomeRails`.**
 * That is a deliberate divergence from "reuse the `saveHomeRails` pattern",
 * not an oversight of it: that action gates on `requireStaffAdmin()`
 * (editorial `admin` only), because it is the platform-wide screen that also
 * edits nav and brand marks for every site in the registry. This screen's
 * own audience is wider on purpose (SURFACES-PLAN's `editor` role exists
 * specifically to publish and curate) and its scope is narrower (this city's
 * `home_rails` column only) — so it is gated by `requireFrontPageEditor()`
 * and calls the same underlying primitives directly: fetch the row
 * (`getRegistrySite`), validate with the SAME function a read uses
 * (`railsFrom` — never a second guess at the shape, for exactly the reason
 * `platform/sites/[slug]/actions.ts`'s own header gives), and write with the
 * same query (`updateSiteHomeRails`). Two callers, one validator, one write —
 * not two validators.
 */

export type FrontPageActionResult = { ok: boolean; message: string }

export async function saveFrontPage(rails: HomeRail[]): Promise<FrontPageActionResult> {
  const actor = await requireFrontPageEditor()

  const slug = process.env.SITE_SLUG
  if (!slug) return { ok: false, message: 'SITE_SLUG is not set on this server.' }

  const site = await getRegistrySite(slug)
  if (!site) return { ok: false, message: 'This site has no registry row yet — see docs/SURFACES-PLAN.md S1.3.' }

  if (rails.length === 0) {
    return { ok: false, message: 'Add at least one band before saving — an empty order is not the same as one band with no pins.' }
  }
  const badIndex = rails.findIndex((r) => !r?.key?.trim())
  if (badIndex !== -1) {
    return { ok: false, message: `Band ${badIndex + 1} has no key. Every band needs one.` }
  }

  const validated = railsFrom(rails)
  if (!validated) {
    return {
      ok: false,
      message:
        'That order was rejected on validation — check that every pin is a whole positive number.',
    }
  }

  await updateSiteHomeRails(slug, validated)
  console.info('[front-page] %s set home_rails for %s (%d band(s))', actor.email, slug, validated.length)
  revalidatePath(FRONT_PAGE_ROOT)
  const ttlSeconds = Number(process.env.SITE_CONFIG_TTL_MS ?? 30_000) / 1000
  return {
    ok: true,
    message: `Saved. Live for readers within ${ttlSeconds} seconds — that is how long the home page's own registry read is cached for.`,
  }
}

/**
 * "Find a story by headline." Title search only, case-insensitive
 * substring — the same `like`-shaped query `ClassificationListView`'s own
 * `q` search runs, kept this simple deliberately: a writer pinning a story
 * knows its headline, not a facet to filter by.
 *
 * Every status is searchable, not published-only: `HomeRail.pins`'s own doc
 * comment says an id that does not resolve to a published article is
 * skipped on read, not an error, so pinning a scheduled story ahead of its
 * own publish is a legitimate, useful thing to do here.
 */
export async function searchArticlesByTitle(q: string): Promise<ArticleSummary[]> {
  await requireFrontPageEditor()
  const query = q.trim()
  if (query.length < 2) return []

  const payload = await payloadClient()
  const { docs } = await payload.find({
    collection: 'articles',
    where: { title: { like: query } },
    sort: '-publishedAt',
    limit: 20,
    depth: 0,
    select: { title: true, slug: true, _status: true, publishedAt: true },
  })

  return docs.map((d) => ({
    id: Number(d.id),
    title: String(d.title ?? `Article ${d.id}`),
    slug: typeof d.slug === 'string' ? d.slug : null,
    status: String(d._status ?? 'draft'),
    publishedAt: typeof d.publishedAt === 'string' ? d.publishedAt : null,
  }))
}

/**
 * Recomputes "what fills the unpinned slots" against the CURRENT pin list in
 * the browser, which has usually moved on from what the page loaded with —
 * an editor who just pinned three stories wants the preview to stop
 * suggesting them. A button rather than an effect that reruns on every
 * keystroke: this is a real query, and re-running it on every pin edit would
 * mean one request per click for a number that is explicitly a preview, not
 * a live total.
 */
export async function refreshAutoFillPreview(bandKey: string, excludeIds: number[]): Promise<ArticleSummary[]> {
  await requireFrontPageEditor()
  return autoFillPreview(bandKey, excludeIds)
}
