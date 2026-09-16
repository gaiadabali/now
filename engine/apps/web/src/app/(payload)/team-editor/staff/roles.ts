import type { CommerceRole, EditorialRole } from '@now/auth'

/**
 * Human labels for the two role dimensions, and the order they are offered in.
 *
 * **Why the vocabulary is not imported from `@now/auth` at runtime.** This
 * module is pulled into a client component, and that package's entry point
 * reaches `node:crypto` and `pg`. A value import would drag both into the
 * browser bundle. `import type` is erased at compile time, so the types still
 * come from the one place that defines them while nothing ships.
 *
 * That leaves the lists themselves duplicated, which is exactly the kind of
 * copy that rots. Two compile-time tethers stop it:
 *
 *   - `Record<EditorialRole, string>` fails the build if a role is added
 *     upstream and not labelled here.
 *   - `satisfies readonly EditorialRole[]` fails it if an order entry names a
 *     role that no longer exists.
 *
 * Neither catches a *duplicate* or a *missing* entry in the order arrays, so
 * `actions.ts` still validates every submitted value against the canonical
 * `isEditorialRole` / `isCommerceRole` before it writes. The labels are a
 * presentation concern; they are not the authority on what is legal.
 */

export const EDITORIAL_LABELS: Record<EditorialRole, string> = {
  admin: 'Administrator',
  editor: 'Editor',
  author: 'Author — drafts only',
  none: 'No editorial access',
}

export const COMMERCE_LABELS: Record<CommerceRole, string> = {
  admin: 'Commerce administrator',
  partner_manager: 'Partner manager',
  viewer: 'Viewer — read only',
  none: 'No commerce access',
}

export const EDITORIAL_ORDER = [
  'admin',
  'editor',
  'author',
  'none',
] as const satisfies readonly EditorialRole[]

export const COMMERCE_ORDER = [
  'admin',
  'partner_manager',
  'viewer',
  'none',
] as const satisfies readonly CommerceRole[]
