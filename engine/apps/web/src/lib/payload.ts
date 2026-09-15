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
  culture: 'culture',
  wellness: 'wellness',
  do: 'things-to-do',
  shop: 'things-to-do',
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
