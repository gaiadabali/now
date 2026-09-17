import type { Access } from 'payload'

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
 * Who may work the classification review queue — see ClassificationReviews.ts.
 *
 * Spelled out as its own export rather than passing `isEditorOrAbove` at the
 * call site, because the two rules only happen to agree today. "May publish"
 * and "may adjudicate what the classifier got wrong" are different questions,
 * and the day a dedicated `reviewer` role appears this is the one line that
 * changes; a collection wired directly to `isEditorOrAbove` would silently
 * keep meaning "publisher".
 *
 * Authors are excluded deliberately. Reviewing is not a stricter kind of
 * editing, it is a different job: the queue is the record of where the
 * engine is wrong, and a decision here is written with `source='editor'`,
 * which §8.A's competitor exclusion then treats as settled fact. That is an
 * adjudication, and it belongs to the people who answer for the taxonomy.
 */
export const isReviewer: Access = ({ req }) => {
  const role = roleOf(req.user)
  return role === 'admin' || role === 'editor'
}

/** The same rule against a plain user object, for nav gating and page guards
 * that have a user but no Payload `req` to hand. */
export const canReview = (user: unknown): boolean => {
  const role = roleOf(user)
  return role === 'admin' || role === 'editor'
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

export { roleOf }
