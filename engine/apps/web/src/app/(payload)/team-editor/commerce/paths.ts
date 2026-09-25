/**
 * Where the commerce console actually lives.
 *
 * These pages were written when the console was its own deployment at the
 * root of its own hostname, and their links still said `/orgs` after the
 * move under `/team-editor/commerce` — every one of them a 404 that nothing
 * failed on, because a `<Link>` to a missing route is only wrong at click
 * time. One constant, imported everywhere, is what stops that recurring the
 * next time the mount point moves.
 *
 * It mirrors `routes.admin` in packages/cms/payload.config.ts plus this
 * folder's name. Those are the two things that have to agree; this file is
 * where the agreement is written down.
 */
export const CONSOLE_ROOT = '/team-editor/commerce'

/** The editorial side of the same admin — Payload's own dashboard. */
export const EDITOR_ROOT = '/team-editor'

export const consoleHref = (path = ''): string => `${CONSOLE_ROOT}${path}`

export const orgHref = (orgId: string): string => consoleHref(`/orgs/${encodeURIComponent(orgId)}`)

/** S5.2 — the new-partnership form for one org. */
export const newPartnershipHref = (orgId: string): string => consoleHref(`/orgs/${encodeURIComponent(orgId)}/partnerships`)

/** S5.2 — the edit form for one existing partnership. */
export const partnershipHref = (orgId: string, partnershipId: string): string =>
  consoleHref(`/orgs/${encodeURIComponent(orgId)}/partnerships/${encodeURIComponent(partnershipId)}`)
