/** URLs for the place desk (plan P1.6). */
export const DESK_ROOT = '/team-editor/place-desk'

export const placeHref = (id: number): string => `${DESK_ROOT}/${id}`

export const QUEUE_FILTERS = ['queue', 'junk', 'suspect', 'region', 'kept'] as const
export type QueueFilterKey = (typeof QUEUE_FILTERS)[number]

export function queueHref(filter: QueueFilterKey, page = 1): string {
  const qs = [filter !== 'queue' ? `show=${filter}` : null, page > 1 ? `page=${page}` : null].filter(Boolean).join('&')
  return qs ? `${DESK_ROOT}?${qs}` : DESK_ROOT
}

/** How many rows one "mark as junk" press writes -- stated on the page,
 * enforced by the action. Each is a Payload write with hooks and a version. */
export const BULK_JUNK_BATCH = 100

/** Queue rows per page. */
export const QUEUE_PAGE_SIZE = 50
