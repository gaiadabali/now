import { notFound } from 'next/navigation'

import { AdminViewFrame, type AdminViewFrameProps } from '../AdminViewFrame'
import { searchParam } from '../searchParams'
import { CommerceOverviewView } from './OverviewView'
import { OrgsListView } from './orgs/OrgsListView'
import { OrgDetailView } from './orgs/[id]/OrgDetailView'
import { NewPartnershipView } from './orgs/[id]/partnerships/NewPartnershipView'
import { EditPartnershipView } from './orgs/[id]/partnerships/[partnershipId]/EditPartnershipView'
import { CampaignsView } from './campaigns/CampaignsView'

/**
 * The commerce console's single door into Payload's admin (S3.1).
 *
 * Same fix, same reasoning as `../classification/ClassificationView.tsx` —
 * read that file's comment for the full argument, including why this wraps
 * its own content in `AdminViewFrame` (`../AdminViewFrame.tsx`): a custom
 * view reached through Payload's generic route fallback gets no template —
 * no sidebar — unless it renders one itself. In short: `commerce/**` was four
 * literal Next routes that shadowed Payload's catch-all and replaced its
 * sidebar with a `console__masthead` whose only way back was an `editor`
 * badge. This is the one Payload custom view (registered at `/commerce` in
 * payload.config.ts) that all four now render behind, so they get the real
 * sidebar instead.
 *
 * The commerce tree has no `:id` vs literal-segment collision the way
 * classification's `review` did — `/commerce/orgs` and `/commerce/campaigns`
 * are both two segments and both literal, and `/commerce/orgs/:id` is three —
 * so the `if`-chain below has no ordering hazard to call out. It still reads
 * top-to-bottom the way the Next.js folder tree it replaces did: shallowest
 * route first.
 */
type Props = Omit<AdminViewFrameProps, 'children' | 'contentClassName' | 'params' | 'searchParams'> & {
  params?: { segments?: string[] } | Record<string, string | string[] | undefined>
  searchParams?: Record<string, string | string[] | undefined>
}

export async function CommerceView({ params, searchParams, ...frame }: Props) {
  const segments = Array.isArray((params as { segments?: string[] } | undefined)?.segments)
    ? ((params as { segments: string[] }).segments)
    : []
  // segments[0] is always 'commerce' — it is what routed us here.
  const rest = segments.slice(1)

  // `.console__main` used to come from the masthead layout this ticket
  // removes. See the identical note in `../classification/ClassificationView.tsx`.
  return (
    <AdminViewFrame {...frame} params={params} searchParams={searchParams} contentClassName="console__main">
      {content(rest, searchParams)}
    </AdminViewFrame>
  )
}

function content(
  rest: string[],
  searchParams: Record<string, string | string[] | undefined> | undefined,
) {
  if (rest.length === 0) return <CommerceOverviewView />

  if (rest.length === 1 && rest[0] === 'orgs') {
    return <OrgsListView searchParams={{ q: searchParam(searchParams, 'q') }} />
  }

  if (rest.length === 1 && rest[0] === 'campaigns') return <CampaignsView />

  if (rest.length === 2 && rest[0] === 'orgs') {
    return <OrgDetailView id={rest[1]} />
  }

  // S5.2 — the partnership write path, nested under the org it belongs to.
  // Still no ordering hazard: `/orgs/:id` (2 segments), `/orgs/:id/partnerships`
  // (3) and `/orgs/:id/partnerships/:partnershipId` (4) are three distinct
  // lengths, so each `if` above still only ever matches its own shape.
  if (rest.length === 3 && rest[0] === 'orgs' && rest[2] === 'partnerships') {
    return <NewPartnershipView orgId={rest[1]} />
  }

  if (rest.length === 4 && rest[0] === 'orgs' && rest[2] === 'partnerships') {
    return <EditPartnershipView orgId={rest[1]} partnershipId={rest[3]} />
  }

  notFound()
}
