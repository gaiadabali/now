/**
 * Where the things the desk home links to actually live.
 *
 * Same reasoning as every other `paths.ts` beside this one (`platform/paths.ts`,
 * `commerce/paths.ts`, `staff/paths.ts`): a link to a moved route is only
 * wrong at click time, so the address is a constant in one place rather than
 * a string repeated across every card.
 */
export const EDITOR_ROOT = '/team-editor'
export const ARTICLES_ROOT = '/team-editor/collections/articles'
export const REVIEW_ROOT = '/team-editor/classification/review'
export const FRONT_PAGE_ROOT = '/team-editor/front-page'
export const MEDIA_CREATE = '/team-editor/collections/media/create'
export const ARTICLE_CREATE = '/team-editor/collections/articles/create'

/**
 * A Payload admin list-view URL, pre-filtered.
 *
 * Payload's List view reads `where` off the URL exactly as its REST API does
 * (`qs`'s bracket notation, the same format `RootPage` already parses every
 * admin request's `searchParams` with) — this is the supported way to deep
 * link "the filtered list" a desk-home count promises, without a second,
 * bespoke list screen duplicating Payload's own.
 */
export function articlesFilteredHref(where: Record<string, unknown>): string {
  const qs = new URLSearchParams()
  encodeWhere(qs, 'where', where)
  return `${ARTICLES_ROOT}?${qs.toString()}`
}

function encodeWhere(qs: URLSearchParams, prefix: string, value: unknown): void {
  if (Array.isArray(value)) {
    value.forEach((item, i) => encodeWhere(qs, `${prefix}[${i}]`, item))
  } else if (value && typeof value === 'object') {
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      encodeWhere(qs, `${prefix}[${k}]`, v)
    }
  } else {
    qs.set(prefix, String(value))
  }
}
