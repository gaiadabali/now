import { notFound } from 'next/navigation'

import { AdminViewFrame, type AdminViewFrameProps } from '../AdminViewFrame'
import { searchParam } from '../searchParams'
import { PlaceDeskPlaceView } from './PlaceView'
import { PlaceDeskQueueView } from './QueueView'

/**
 * The place desk's door into Payload's admin (plan P1.6), registered against
 * `/place-desk` in `admin.components.views` (payload.config.ts). One view,
 * routed by hand, for the reason `../classification/ClassificationView.tsx`
 * gives: Payload matches the first registered pattern, so a literal and a
 * dynamic segment are safer decided in one `if`-chain than by config order.
 *
 *   /team-editor/place-desk        the queue
 *   /team-editor/place-desk/:id    one place
 */
type Props = Omit<AdminViewFrameProps, 'children' | 'contentClassName' | 'params' | 'searchParams'> & {
  params?: { segments?: string[] } | Record<string, string | string[] | undefined>
  searchParams?: Record<string, string | string[] | undefined>
}

export async function PlaceDeskView({ params, searchParams, ...frame }: Props) {
  const segments = Array.isArray((params as { segments?: string[] } | undefined)?.segments)
    ? (params as { segments: string[] }).segments
    : []
  const rest = segments.slice(1)

  return (
    <AdminViewFrame {...frame} params={params} searchParams={searchParams} contentClassName="classify__main place-desk">
      {content(rest, searchParams)}
    </AdminViewFrame>
  )
}

function content(rest: string[], searchParams: Record<string, string | string[] | undefined> | undefined) {
  if (rest.length === 0) {
    return <PlaceDeskQueueView searchParams={{ show: searchParam(searchParams, 'show'), page: searchParam(searchParams, 'page') }} />
  }
  if (rest.length === 1 && /^\d+$/.test(rest[0]!)) {
    return <PlaceDeskPlaceView id={rest[0]!} />
  }
  notFound()
}
