import type { CollectionBeforeChangeHook } from 'payload'

/**
 * `articles.createdBy` — approved as a follow-up to the desk home's "my
 * drafts", which had no reliable way to answer "is this yours": `author` is
 * the public byline (`Authors.ts`'s own header — "not to `users`"), and there
 * was no column linking a document to the CMS login that started it.
 *
 * **Stamped once, on the operation that creates the document, and never
 * touched again.** `operation === 'create'` is Payload's own signal for
 * this — not "does the doc already have a value", which would also fire on
 * every autosave of a document imported before this field existed and
 * silently attribute someone else's decade-old draft to whoever happened to
 * autosave it next. A field that can be silently reassigned is not an
 * audit trail.
 *
 * `req.user` is absent only for an unauthenticated request, which every
 * verb on this collection already requires a role for (`access.create` /
 * `access.update` — `isAuthorOrAbove`); this hook never runs without one in
 * practice.
 *
 * **Only a genuine numeric id is written.** Found by running this repo's own
 * `verify-rbac-publish-gate.mjs`, which calls the Local API with a synthetic
 * `user: { id: 'verify-author', role: 'author' }` to exercise the role gate
 * without a real account — a legitimate, existing pattern this hook must not
 * break. Writing that string straight into a relationship column fails
 * Payload's own field validation (a `users` row's id is numeric here), which
 * is the right outcome generalised: a `createdBy` this hook cannot confirm is
 * a real `users` row should be left NULL, not a foreign key pointed at
 * nothing.
 */
export const stampCreatedBy: CollectionBeforeChangeHook = ({ data, operation, req }) => {
  if (operation === 'create') {
    const id = req.user?.id
    data.createdBy = typeof id === 'number' ? id : undefined
  }
  return data
}
