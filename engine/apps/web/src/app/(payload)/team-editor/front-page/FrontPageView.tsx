import { canEditFrontPage, requireUser } from '@/lib/auth'

import { AdminViewFrame, type AdminViewFrameProps } from '../AdminViewFrame'
import { autoFillPreview, getFrontPageState, resolveArticleSummaries } from './data'
import type { ArticleSummary } from './data'
import { bandHoldsStories } from './paths'
import { FrontPageEditor } from './FrontPageEditor'

/**
 * `/team-editor/front-page` — the front-page editor's one door into
 * Payload's admin.
 *
 * Registered in `payload.config.ts`'s `admin.components.views` under a NEW
 * key (`frontPage`, `path: '/front-page'`), appended after the existing four
 * (classification/commerce/staff/platform). S3.1's own comment on that block
 * warns that `path` is matched by PREFIX and Payload takes the first entry
 * in object order whose path matches — `/front-page` shares no prefix with
 * any of `/classification`, `/commerce`, `/staff` or `/platform`, so there is
 * no ordering hazard to reason about here the way there is between, say, a
 * literal and a dynamic segment at the same depth. Wrapped in
 * `AdminViewFrame` for the same reason every one of those four is: a custom
 * view reached through Payload's generic route fallback gets no sidebar
 * template unless it renders `DefaultTemplate` itself.
 *
 * **Role decision, stated once so it does not have to be inferred from the
 * code:** editor and admin can edit; an author who navigates here directly
 * gets a READ-ONLY render, not a redirect. `NavFrontPage` (the sidebar link)
 * is hidden from authors the same way `NavReview`/`NavPlatform` hide theirs —
 * but unlike a review queue's evidence or a partner's commercial terms, the
 * front page's current layout is not confidential: it is what every reader
 * already sees on arrival. Redirecting an author away from a screen that
 * only shows them today's public home page would be hiding information for
 * no protective reason; showing it without edit controls is not.
 */
type Props = Omit<AdminViewFrameProps, 'children' | 'contentClassName' | 'params' | 'searchParams'> & {
  params?: { segments?: string[] } | Record<string, string | string[] | undefined>
  searchParams?: Record<string, string | string[] | undefined>
}

export async function FrontPageView({ params, searchParams, ...frame }: Props) {
  const user = await requireUser()
  const canEdit = canEditFrontPage(user)

  const state = await getFrontPageState()

  const allPinIds = state.rails.flatMap((b) => b.pins ?? [])
  const [summaries, autoFillEntries] = await Promise.all([
    resolveArticleSummaries(allPinIds),
    Promise.all(
      state.rails
        .filter((b) => bandHoldsStories(b.key))
        .map(async (b) => [b.key, await autoFillPreview(b.key, b.pins ?? [])] as const),
    ),
  ])

  const initialSummaries: Record<number, ArticleSummary> = {}
  for (const [id, summary] of summaries) initialSummaries[id] = summary
  const initialAutoFill: Record<string, ArticleSummary[]> = {}
  for (const [key, preview] of autoFillEntries) initialAutoFill[key] = preview

  return (
    <AdminViewFrame {...frame} params={params} searchParams={searchParams} contentClassName="fp__main">
      <h1>Front page</h1>
      {!canEdit ? (
        <p className="fp__sub">
          You can see today&rsquo;s band order here, but only an editor or admin can change it.
        </p>
      ) : null}
      <FrontPageEditor
        governed={state.governed}
        initialAutoFill={initialAutoFill}
        initialRails={state.rails}
        initialSummaries={initialSummaries}
        readOnly={!canEdit}
        siteName={state.siteName}
        ttlSeconds={state.ttlSeconds}
      />
    </AdminViewFrame>
  )
}
