import 'server-only'

import { getRelated, type Article } from '@/lib/content'

/**
 * What the reader site asks the engine for, and nothing else.
 *
 * This file is a CONTRACT first and an implementation second. Two pieces of
 * work build against it at once: the recommendation engine fills in the
 * bodies, and the reader redesign renders whatever comes back. Neither should
 * need to open the other's files to do its job, which is why the page never
 * learns how a rail was chosen — it gets rails, in order, already labelled.
 *
 * ## The one rule the page must never break
 *
 * On a venue story, nothing on the page may suggest a competitor of that
 * venue. A hotel story never suggests a hotel (or a villa, or a resort — the
 * rule is the L1 `type`, ARCHITECTURE §4). A restaurant story never suggests a
 * restaurant, a café or any other food-and-drink venue. The owner's words,
 * twice (2026-09-11 and 2026-09-24): suggest the *other* things a reader
 * needs — somewhere to eat after the hotel, somewhere to stay after dinner.
 *
 * That rule is enforced HERE and in the engine, never in a component. A page
 * that adds its own "More from this section" rail under a hotel story has
 * broken it, however the rail is styled.
 */

/** A story placed in a rail. `rail` and `position` feed the beacon (§10). */
export type RailArticle = Article & {
  rail: string
  /** 1-indexed slot. The beacon needs it on the impression AND the click. */
  position: number
}

export type ArticleRail = {
  /** Stable key — also the beacon's `data-nowb-rail`. */
  key: string
  /** Bebas kicker. Information, not decoration (DESIGN-SYSTEM §2). */
  kicker: string
  title: string
  items: RailArticle[]
}

/**
 * Who is reading. Every field is optional: an anonymous first visit is the
 * common case and must get a good page, not a degraded one.
 */
export type ReaderContext = {
  /** The beacon's anonymous id, when the reader has one. */
  anonId?: string
  /** A signed-in reader (`engine.identities.id`). */
  identityId?: string
}

/**
 * Every recommendation rail for one article page, in the order the page
 * should render them. May be empty; the page renders no rail rather than an
 * empty one.
 *
 * STUB: delegates to the old same-page heuristic until the engine body lands.
 */
export async function getArticleRails(article: Article, _reader: ReaderContext = {}): Promise<ArticleRail[]> {
  const items = await getRelated(article)
  if (items.length === 0) return []
  return [
    {
      key: 'read-next',
      kicker: 'Keep reading',
      title: 'Read Next',
      items: items.map((a, i) => ({ ...a, rail: 'read-next', position: i + 1 })),
    },
  ]
}

/**
 * The home page's personal rail. `null` when there is nothing personal to say
 * yet (no history, no stated preferences) — the home page then renders no
 * "For you" band at all rather than relabelling recency as taste.
 *
 * STUB: returns null until the engine body lands.
 */
export async function getForYou(_reader: ReaderContext = {}, _limit = 6): Promise<ArticleRail | null> {
  return null
}
