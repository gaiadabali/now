import type { Access, FieldAccess } from 'payload'

export type Role = 'admin' | 'editor' | 'author'

function roleOf(user: unknown): Role | null {
  if (user && typeof user === 'object' && 'role' in user) {
    const role = (user as { role?: unknown }).role
    if (role === 'admin' || role === 'editor' || role === 'author') return role
  }
  return null
}

/** Any authenticated CMS user (admin, editor or author). */
export const isLoggedIn: Access = ({ req }) => Boolean(req.user)

/** Admins only. */
export const isAdmin: Access = ({ req }) => roleOf(req.user) === 'admin'

/** Editors and admins — the roles allowed to publish and delete. */
export const isEditorOrAbove: Access = ({ req }) => {
  const role = roleOf(req.user)
  return role === 'admin' || role === 'editor'
}

/** Any logged-in user may create/read; used for collections without a
 * meaningful per-row ownership concept (Places, Media, Events, Authors). */
export const isAuthorOrAbove: Access = ({ req }) => {
  const role = roleOf(req.user)
  return role === 'admin' || role === 'editor' || role === 'author'
}

/**
 * Field-level gate on the publish transition. Authors may save drafts and
 * edit their own articles freely, but only editor/admin can move an
 * article's status to "published" — enforced in the Articles collection's
 * `beforeChange` hook (`src/hooks/enforcePublishRole.ts`), not here; this
 * export exists so the same role check is reused in both places instead of
 * duplicated.
 */
export const canPublish = (user: unknown): boolean => {
  const role = roleOf(user)
  return role === 'admin' || role === 'editor'
}

export const readOnlyForAuthors: FieldAccess = ({ req }) => canPublish(req.user)

export { roleOf }
