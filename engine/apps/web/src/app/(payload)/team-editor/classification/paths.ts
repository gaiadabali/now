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

/** The review desk — the queue grouped by the pattern behind each mistake. */
export const REVIEW_ROOT = `${CLASSIFY_ROOT}/review`

/**
 * One cluster's workbench.
 *
 * The three parts of the key travel as query parameters rather than path
 * segments because `legacyCategory` is a WordPress category name, verbatim —
 * "Restaurants and Bars", "Art In Bali" — and a path segment would have to
 * survive two rounds of slug-and-unslug to come back as the exact string the
 * SQL equality needs. A query parameter is the same value in and out.
 */
export const clusterHref = (key: {
  facetKey: string
  legacyCategory: string
  proposedValue: string
}): string =>
  `${REVIEW_ROOT}/cluster?facet=${encodeURIComponent(key.facetKey)}` +
  `&legacy=${encodeURIComponent(key.legacyCategory)}` +
  `&value=${encodeURIComponent(key.proposedValue)}`
