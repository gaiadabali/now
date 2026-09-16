'use client'

import { usePathname, useSearchParams } from 'next/navigation'
import { useEffect, useRef } from 'react'

/**
 * Keeps the beacon in step with client-side navigation, and registers what the
 * rails put in front of the reader.
 *
 * ## Why it has to exist
 *
 * `<script>` runs once per document. This app navigates without one: after the
 * first load every link is a client-side transition, so the beacon's config —
 * read from its own tag and the `nowb:*` meta at boot — freezes on the landing
 * page. Driven in Chromium before this component: land on the home page, click
 * through to an article, read it, leave. One `view`, of the home page, and a
 * `dwell` attributed to `surface: site` with no entity. The article was never
 * recorded as read. That is the shape of most real sessions.
 *
 * ## Why it reads the DOM instead of taking props
 *
 * The entity is declared by the page as `<meta name="nowb:entity">` (see
 * `Beacon.tsx`), and this component lives in the layout, which does not know
 * which page it is wrapping. Reading the meta is what lets ONE component cover
 * every route — including the routes that name no entity, which a per-page
 * prop could never reach because those pages render no beacon component at
 * all. The alternative, threading entity props from every page through the
 * layout, is the per-page wiring `Beacon.tsx` deliberately avoided.
 *
 * Same argument for impressions: a card that is tagged for click attribution
 * (`data-nowb-entity` + `data-nowb-rail` + `data-nowb-position`, see
 * `StoryCard.tsx`) is by definition a card a rail rendered. Scraping those
 * attributes means adding a rail is one change, not two, and the impression
 * cannot silently disagree with the click it will later be joined to.
 *
 * ## Ordering
 *
 * The beacon tag is `async`, so it may not have run when this effect does. The
 * queuing shim from the beacon's README covers that: calls made before the
 * script installs itself are replayed, in order, the moment it does.
 */

type Queued = { (...args: unknown[]): void; q?: unknown[][]; __loaded?: boolean }

function nowb(): Queued {
  const w = window as unknown as { NOWB?: Queued }
  if (!w.NOWB) {
    const shim: Queued = function (...args: unknown[]) {
      ;(shim.q = shim.q || []).push(args)
    }
    w.NOWB = shim
  }
  return w.NOWB
}

function metaContent(name: string): string | undefined {
  const el = document.querySelector(`meta[name="nowb:${name}"]`)
  return el?.getAttribute('content') || undefined
}

export function BeaconRoute() {
  const pathname = usePathname()
  // A section index filtered by facet, and page 2 of it, are different pages
  // to a reader even though the pathname is identical.
  const searchParams = useSearchParams()
  const key = `${pathname}?${searchParams?.toString() ?? ''}`

  // Impressions are per page view and must not be sent twice for the same
  // card. React's StrictMode runs effects twice in development on purpose;
  // without this the tables would carry double the impressions of reality,
  // which is worse than none because it looks plausible.
  const registered = useRef<Set<string>>(new Set())
  const lastKey = useRef<string | null>(null)

  useEffect(() => {
    const send = nowb()

    if (lastKey.current !== key) {
      registered.current = new Set()
      lastKey.current = key
      // A no-op in the beacon when it names the page already in view, which
      // is exactly the case on the initial load its own boot `view` covered.
      send('page', {
        entity: metaContent('entity'),
        entityType: metaContent('entity-type'),
        surface: metaContent('surface') ?? 'site',
      })
    }

    const surface = metaContent('surface') ?? 'site'
    document.querySelectorAll<HTMLElement>('[data-nowb-rail][data-nowb-entity]').forEach((el) => {
      const entityId = el.dataset.nowbEntity
      const rail = el.dataset.nowbRail
      const position = Number(el.dataset.nowbPosition)
      if (!entityId || !rail || !Number.isFinite(position)) return
      const dedupe = `${key}|${rail}|${position}|${entityId}`
      if (registered.current.has(dedupe)) return
      registered.current.add(dedupe)
      send('impression', { surface, rail, entityId, position })
    })
  }, [key])

  return null
}
