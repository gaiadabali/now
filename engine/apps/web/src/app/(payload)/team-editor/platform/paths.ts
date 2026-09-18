/**
 * Where the platform console lives.
 *
 * Same reasoning as `commerce/paths.ts` and `staff/paths.ts`: a `<Link>` to a
 * moved route is only wrong at click time, so the mount point is a constant
 * rather than a string repeated across pages, `revalidatePath` calls and the
 * lint that checks every collection is grouped. D-S1 (docs/SURFACES-PLAN.md
 * §3) put this section under `/team-editor` rather than a fourth app, so
 * `EDITOR_ROOT` is the same address the other two admin sections use to link
 * back to Payload's own dashboard.
 */
export const PLATFORM_ROOT = '/team-editor/platform'

/** Payload's own dashboard — the editorial side of the same admin. */
export const EDITOR_ROOT = '/team-editor'

export const platformHref = (path = ''): string => `${PLATFORM_ROOT}${path}`

export const siteHref = (slug: string): string => `${PLATFORM_ROOT}/sites/${encodeURIComponent(slug)}`
