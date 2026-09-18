import { notFound } from 'next/navigation'

import { AdminViewFrame, type AdminViewFrameProps } from '../AdminViewFrame'
import { RegistryIndexView } from './RegistryIndexView'
import { SiteDetailView } from './sites/[slug]/SiteDetailView'

/**
 * The platform console's single door into Payload's admin.
 *
 * **Why this file exists at all, when S5.1 had already shipped working
 * pages.** S5.1 and S3.1 were built in parallel, and they met at a path
 * rather than at a mechanism. S5.1 built `/team-editor/platform` as literal
 * Next routes (`page.tsx`), while S3.1 was in the middle of proving that a
 * literal route under `(payload)/team-editor/**` *shadows Payload's
 * catch-all* — which is precisely how classification, commerce and staff came
 * to have no sidebar and need three bespoke mastheads instead.
 *
 * So the one screen S3.1 added a sidebar link for was the one screen that
 * rendered outside the sidebar. Caught by checking, not by either report: the
 * admin routes all returned 200 with the right content, and `/commerce`
 * carried `<aside class="nav">` while `/platform` carried none.
 *
 * The fix is to do here exactly what the other three areas do — one custom
 * view registered in `payload.config.ts`, prefix-matched, dispatching over
 * the leftover segments, with its content wrapped in `AdminViewFrame` so it
 * gets Payload's real chrome. See `../commerce/CommerceView.tsx` for the
 * fuller argument and `../AdminViewFrame.tsx` for why the wrapper is needed
 * (a custom view reached through Payload's generic route fallback gets no
 * template unless it renders one itself).
 *
 * No ordering hazard in the chain below: `/platform` is the index and
 * `/platform/sites/:slug` is the only child, three segments deep against the
 * index's one. Shallowest first, the way the folder tree it replaces read.
 */
type Props = Omit<AdminViewFrameProps, 'children' | 'contentClassName' | 'params' | 'searchParams'> & {
  params?: { segments?: string[] } | Record<string, string | string[] | undefined>
  searchParams?: Record<string, string | string[] | undefined>
}

export async function PlatformView({ params, searchParams, ...frame }: Props) {
  const segments = Array.isArray((params as { segments?: string[] } | undefined)?.segments)
    ? (params as { segments: string[] }).segments
    : []
  // segments[0] is always 'platform' — it is what routed us here.
  const rest = segments.slice(1)

  return (
    <AdminViewFrame {...frame} params={params} searchParams={searchParams} contentClassName="platform__main">
      {content(rest)}
    </AdminViewFrame>
  )
}

function content(rest: string[]) {
  if (rest.length === 0) return <RegistryIndexView />

  // `sites` is a segment rather than the index so the area has room for the
  // rest of S5 — partnerships, syndication, classification health — without
  // the registry having claimed the root.
  if (rest.length === 2 && rest[0] === 'sites') return <SiteDetailView slug={rest[1]} />

  notFound()
}
