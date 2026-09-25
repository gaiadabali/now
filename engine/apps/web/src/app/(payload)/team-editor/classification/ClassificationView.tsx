import { notFound } from 'next/navigation'

import { AdminViewFrame, type AdminViewFrameProps } from '../AdminViewFrame'
import { searchParam } from '../searchParams'
import { ClassificationListView } from './ListView'
import { ClassificationReportView } from './[id]/ReportView'
import { ReviewDeskView } from './review/ReviewDeskView'
import { ClusterWorkbenchView } from './review/cluster/ClusterWorkbenchView'

/**
 * The classification report tree's single door into Payload's admin (S3.1).
 *
 * BEFORE THIS FILE, `classification/**` was four literal Next routes
 * (`page.tsx`, `[id]/page.tsx`, `review/page.tsx`, `review/cluster/page.tsx`)
 * that lived under `(payload)` but OUTSIDE Payload's own catch-all
 * (`team-editor/[[...segments]]/page.tsx`). Next resolves a literal route
 * before a catch-all at the same level, so those four files silently shadowed
 * Payload's router for every URL under `/team-editor/classification` — which
 * is exactly why they never got Payload's sidebar: they replaced it with their
 * own `classify__masthead`, whose only way back to the rest of the admin was
 * a small `editor` badge in the corner (docs/SURFACES-PLAN.md, S3.1).
 *
 * The fix is to stop shadowing the catch-all. Every one of those four files is
 * gone as a ROUTE; their content now lives in the plain components imported
 * above, and Payload renders exactly this one — registered against
 * `/classification` in `admin.components.views` (payload.config.ts). See that
 * config for why the import path looks the way it does (a `@/…` specifier,
 * resolved through THIS APP's import map and tsconfig, not the CMS package's)
 * — and see `../AdminViewFrame.tsx` for why this file wraps its own content
 * in `DefaultTemplate` rather than getting it for free: a custom view
 * reached through Payload's generic route fallback (every path here, since
 * none of them is one of Payload's built-in view names) is NOT given a
 * template by `getRouteData`, sidebar included, unless the view renders one
 * itself.
 *
 * WHY ONE VIEW DOES ITS OWN ROUTING BY HAND, INSTEAD OF FOUR NARROWER
 * REGISTRATIONS. Payload matches a custom view's `path` with `path-to-regexp`
 * and picks the FIRST entry in `admin.components.views` whose pattern matches
 * — there is no "most specific wins" rule the way Next's file router has one.
 * `/classification/review` and `/classification/:id` are both two segments,
 * so a dynamic `:id` pattern registered before the literal `review` path would
 * swallow it (`id: 'review'`) with nothing to say otherwise. Four
 * registrations means four chances to get that ordering right, forever, for
 * every reader of payload.config.ts. One registration with an ordinary
 * `if`-chain below reads the same way the Next.js folder tree it replaces used
 * to route: literal segments before dynamic ones, which is a decision every
 * one of the branches below states once rather than being an artefact of
 * where a config key sits in an object literal.
 *
 * A second reason this is one file: it is also what keeps the browser tab
 * title honest. `admin.components.views` carries one static `meta.title` per
 * registered path. Splitting this into four registrations would not have
 * given four titles — the four Next pages being replaced never set their own
 * `metadata` either, only `classification/layout.tsx` did, uniformly, and
 * that layout (and its title) is one of the things this ticket removes. One
 * view, one title ("Classification"), same as every reader of this surface
 * has always seen.
 */
type Props = Omit<AdminViewFrameProps, 'children' | 'contentClassName' | 'params' | 'searchParams'> & {
  params?: { segments?: string[] } | Record<string, string | string[] | undefined>
  searchParams?: Record<string, string | string[] | undefined>
}

export async function ClassificationView({ params, searchParams, ...frame }: Props) {
  const segments = Array.isArray((params as { segments?: string[] } | undefined)?.segments)
    ? ((params as { segments: string[] }).segments)
    : []
  // segments[0] is always 'classification' — it is what routed us here — so
  // only what comes after it decides which screen this request wants.
  const rest = segments.slice(1)

  // `.classify__main` used to come from the masthead layout this ticket
  // removes (`max-width`, the gutter, the padding under Payload's own app
  // header). One wrapper here does the same job for all four screens, so
  // `report.css` (now folded into styles/admin.css) did not need a single
  // selector rewritten.
  return (
    <AdminViewFrame {...frame} params={params} searchParams={searchParams} contentClassName="classify__main">
      {content(rest, searchParams)}
    </AdminViewFrame>
  )
}

function content(
  rest: string[],
  searchParams: Record<string, string | string[] | undefined> | undefined,
) {
  if (rest.length === 0) {
    return (
      <ClassificationListView
        searchParams={{
          q: searchParam(searchParams, 'q'),
          all: searchParam(searchParams, 'all'),
        }}
      />
    )
  }

  if (rest.length === 1 && rest[0] === 'review') {
    return (
      <ReviewDeskView
        searchParams={{ facet: searchParam(searchParams, 'facet'), page: searchParam(searchParams, 'page') }}
      />
    )
  }

  if (rest.length === 2 && rest[0] === 'review' && rest[1] === 'cluster') {
    return (
      <ClusterWorkbenchView
        searchParams={{
          facet: searchParam(searchParams, 'facet'),
          legacy: searchParam(searchParams, 'legacy'),
          value: searchParam(searchParams, 'value'),
        }}
      />
    )
  }

  if (rest.length === 1) {
    return <ClassificationReportView id={rest[0]} />
  }

  notFound()
}
