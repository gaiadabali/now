import type { CollectionConfig } from 'payload'

import { isAdmin, readOnlyForAuthors } from '@/access'
import { platformStrategy } from '@/auth/platformStrategy'

/**
 * `users` — shadow projections of the platform identity store. Roles per
 * ARCHITECTURE.md editorial essentials: editor / author / admin.
 *   - admin:  full access, including user management and deletes
 *   - editor: publish, delete content, cannot manage other users' roles
 *   - author: create/edit own drafts, cannot publish (enforced in
 *     `src/hooks/enforcePublishRole.ts`) or delete
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
  admin: { useAsTitle: 'email', defaultColumns: ['email', 'role'] },
  access: {
    read: () => true,
    create: isAdmin,
    update: isAdmin,
    delete: isAdmin,
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
      admin: { description: 'Matched against the platform identity store at sign-in.' },
    },
    {
      name: 'role',
      type: 'select',
      required: true,
      defaultValue: 'author',
      options: ['admin', 'editor', 'author'],
      access: {
        // Only an editor/admin may change someone's role.
        update: readOnlyForAuthors,
      },
    },
    { name: 'name', type: 'text' },
  ],
}
