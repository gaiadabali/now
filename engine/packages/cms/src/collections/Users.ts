import type { CollectionConfig } from 'payload'

import { platformStrategy } from '../auth/platformStrategy'
import { GROUPS } from './groups'

/**
 * `users` — shadow projections of the platform identity store.
 *
 * The `role` column here is what every other collection's access rules read,
 * per ARCHITECTURE.md's editorial essentials:
 *   - admin:  full access, including deletes
 *   - editor: publish and delete content
 *   - author: create/edit own drafts, cannot publish (enforced in
 *     `src/hooks/enforcePublishRole.ts`) or delete
 *
 * It is READ here and written only by the sign-in upsert — see the access
 * block below. Managing who has which role is the platform's job, not this
 * collection's, and the rows are a cache of that decision.
 */
export const Users: CollectionConfig = {
  slug: 'users',
  // Identity is NOT owned here. Rows in this table are shadow projections of
  // `now_platform.public.users`, written at sign-in by
  // `src/app/(payload)/api/staff-login` and carrying a role but never a
  // credential (docs/ADMIN-CONSOLIDATION.md, Phase 1).
  //
  // `disableLocalStrategy` is the load-bearing line. Without it Payload would
  // still accept a password against this table. The shadow rows have NULL
  // hash/salt so none of them could authenticate — but any row an admin
  // created by hand *would*, quietly reintroducing a second, unmanaged way in
  // that bypasses the platform's lockout, roles and password policy entirely.
  auth: {
    disableLocalStrategy: true,
    strategies: [{ name: 'platform-identity', authenticate: platformStrategy }],
  },
  admin: {
    group: GROUPS.settings,
    useAsTitle: 'email',
    defaultColumns: ['email', 'role'],
    description:
      'A read-only mirror of the platform identity store. Accounts and roles ' +
      'are managed there; every field here is rewritten at the user’s next sign-in.',
  },
  // Read-only, and that is the design rather than a restriction.
  //
  // Every row here is a projection, rewritten from `now_platform.public.users`
  // by the raw upsert in `@now/auth`'s `upsertShadowUser` on EVERY sign-in:
  //
  //     ON CONFLICT (email) DO UPDATE SET name = …, role = …
  //
  // docs/ADMIN-CONSOLIDATION.md states the same thing from the other side —
  // "Role is re-read from the platform on every sign-in" — which is what
  // makes a revoked role take effect. The cost is that an edit made here is
  // not rejected, it is *accepted and then silently discarded*: an admin
  // demotes someone, the UI says saved, and their next sign-in restores the
  // old role with nothing logged anywhere. Refusing the write is the honest
  // behaviour; the field descriptions below say where the real value lives.
  //
  // This does not weaken anything. The upsert runs on a direct pool and
  // never passes through Payload, so these rules gate the admin UI only —
  // which is exactly the surface that was lying.
  access: {
    read: () => true,
    // Creating a row here makes a user with NULL hash/salt who cannot sign
    // in; the platform is where an account begins.
    create: () => false,
    update: () => false,
    // Deleting one changes nothing either: the next sign-in recreates it.
    delete: () => false,
  },
  fields: [
    // Declared EXPLICITLY, which it would not need to be with Payload's local
    // strategy. `disableLocalStrategy: true` removes the auth fields Payload
    // normally synthesises -- email among them -- so without this the document
    // comes back as { id, role, name, updatedAt, createdAt } and every lookup
    // by email silently sees `undefined`. The column already exists in the
    // database from when this collection used `auth: true`, so this maps onto
    // it rather than adding anything.
    {
      name: 'email',
      type: 'email',
      required: true,
      unique: true,
      index: true,
      admin: {
        readOnly: true,
        description:
          'Matched against the platform identity store at sign-in, and the key the ' +
          'shadow upsert conflicts on. Changing it here would orphan this row rather ' +
          'than rename the account.',
      },
    },
    {
      name: 'role',
      type: 'select',
      required: true,
      defaultValue: 'author',
      // 'none' is required, not cosmetic. Shadow rows are written from the
      // platform's editorial_role (docs/ADMIN-CONSOLIDATION.md Phase 1), and
      // that dimension has a 'none' value for staff with no publishing
      // rights — a commerce-only user, say. Without it here the upsert fails
      // on the enum and that person cannot sign in AT ALL, which is a lockout
      // dressed up as a database error.
      options: ['admin', 'editor', 'author', 'none'],
      admin: {
        readOnly: true,
        description:
          'Mirrored from the platform’s editorial_role on every sign-in. Change it ' +
          'in the platform identity store; a change made here would be reverted.',
      },
    },
    { name: 'name', type: 'text', admin: { readOnly: true } },
  ],
}
