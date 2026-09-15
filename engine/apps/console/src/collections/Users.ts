import type { CollectionConfig } from 'payload'

/**
 * `users` — console login accounts (Payload `auth: true`).
 *
 * Separate from the CMS's `users` table on purpose. That one lives in each
 * *city* database and gates editorial work; this one lives in the platform
 * database and gates commercial data. An editor who can publish an article
 * in Jakarta should not thereby be able to read every partner's contract
 * terms, and the two tables being in different databases makes that the
 * default rather than something access rules have to remember.
 *
 * Roles are deliberately coarse — there are three kinds of person who open
 * this tool, not a permission matrix:
 *
 *   - admin           full access, including managing other console users
 *   - partner_manager reads everything, and will own the editing surface
 *                     when E4.4 adds one
 *   - viewer          read-only; for anyone who needs the numbers but must
 *                     not change a commercial arrangement
 *
 * Every role is read-only against commerce data today, because the console
 * has no write surface yet (see payload.config.ts). The distinction between
 * partner_manager and viewer exists now so that adding writes later is a
 * change to access rules, not a migration of everyone's role.
 */

// Who may administer ACCOUNTS. This collection is the access-control list for
// commercial data, so the commerce dimension is the one that governs it —
// an editorial admin in a city has no business granting partner access.
const isAdmin = ({ req }: { req: { user?: { commerceRole?: string } | null } }) =>
  req.user?.commerceRole === 'admin'

export const Users: CollectionConfig = {
  slug: 'users',
  auth: {
    // Eight hours: long enough for a working day, short enough that a
    // forgotten session on a shared machine expires the same day.
    tokenExpiration: 60 * 60 * 8,
    // Commercial data behind a login that allows unlimited guesses is a
    // login in name only.
    maxLoginAttempts: 8,
    lockTime: 10 * 60 * 1000,
  },
  admin: {
    useAsTitle: 'email',
    defaultColumns: ['email', 'name', 'editorialRole', 'commerceRole'],
  },
  access: {
    // A signed-in user may see who else has access; only an admin may
    // change it. `read: () => true` would be wrong here — this collection
    // is the access-control list for commercial data.
    read: ({ req }) => Boolean(req.user),
    create: isAdmin,
    update: ({ req, id }) => {
      if (req.user?.commerceRole === 'admin') return true
      // Anyone may edit their own row (name, password) but not someone
      // else's, and the `role` field below is admin-only regardless.
      return req.user?.id === id
    },
    delete: isAdmin,
  },
  fields: [
    // TWO DIMENSIONS, NOT ONE ENUM.
    //
    // The CMS and this console arrived with disjoint vocabularies —
    // admin|editor|author for publishing, admin|partner_manager|viewer for
    // commercial data. docs/ADMIN-CONSOLIDATION.md merges the surfaces, so
    // one account has to express both, and a single field cannot: "an editor
    // who may also read partner terms" and "a partner manager who may not
    // publish" are both real people. Collapsing them forces either
    // over-granting or an enum that grows multiplicatively.
    //
    // `none` is the default on both. A role model whose safe state depends on
    // remembering to set something is a role model that will leak.
    {
      name: 'editorialRole',
      type: 'select',
      required: true,
      defaultValue: 'none',
      options: [
        { label: 'Admin', value: 'admin' },
        { label: 'Editor', value: 'editor' },
        { label: 'Author', value: 'author' },
        { label: 'No editorial access', value: 'none' },
      ],
      admin: { description: 'What this person may do in the city CMS.' },
      access: {
        // Without this, the self-edit rule above would let any user
        // promote themselves.
        update: isAdmin,
      },
    },
    {
      name: 'commerceRole',
      type: 'select',
      required: true,
      defaultValue: 'none',
      options: [
        { label: 'Admin', value: 'admin' },
        { label: 'Partner manager', value: 'partner_manager' },
        { label: 'Viewer', value: 'viewer' },
        { label: 'No commercial access', value: 'none' },
      ],
      admin: { description: 'What this person may see of orgs, partnerships and campaigns.' },
      access: {
        update: isAdmin,
      },
    },
    { name: 'name', type: 'text' },
  ],
}
