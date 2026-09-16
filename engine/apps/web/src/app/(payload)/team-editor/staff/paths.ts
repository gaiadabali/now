/**
 * Where the staff surface lives.
 *
 * Same reasoning as `commerce/paths.ts`: a `<Link>` to a moved route is only
 * wrong at click time, so the mount point is a constant rather than a string
 * repeated across pages and `revalidatePath` calls. It mirrors `routes.admin`
 * in packages/cms/payload.config.ts plus this folder's name.
 */
export const STAFF_ROOT = '/team-editor/staff'

/** Payload's own dashboard — the editorial side of the same admin. */
export const EDITOR_ROOT = '/team-editor'
