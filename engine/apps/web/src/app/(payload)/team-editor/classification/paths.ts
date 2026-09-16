/**
 * Where the classification report lives.
 *
 * Same job as the commerce console's `paths.ts`, and it exists for the same
 * reason that file gives: a `<Link>` to a moved route is only wrong at click
 * time, so the mount point is written down once rather than spelled out in
 * every page.
 */
export const CLASSIFY_ROOT = '/team-editor/classification'

/** The editorial side of the same admin — Payload's own dashboard. */
export const EDITOR_ROOT = '/team-editor'

export const classifyHref = (path = ''): string => `${CLASSIFY_ROOT}${path}`

/** The Payload edit form for one article — the surface this report replaces. */
export const articleEditHref = (id: number): string => `${EDITOR_ROOT}/collections/articles/${id}`

/** One row of the review queue, in Payload's own admin. */
export const reviewEditHref = (id: number): string =>
  `${EDITOR_ROOT}/collections/classification-reviews/${id}`
