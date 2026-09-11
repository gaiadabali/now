import type { CollectionConfig } from 'payload'

import { isAdmin, readOnlyForAuthors } from '@/access'

/**
 * `users` — CMS login accounts (Payload `auth: true`). Roles per
 * ARCHITECTURE.md editorial essentials: editor / author / admin.
 *   - admin:  full access, including user management and deletes
 *   - editor: publish, delete content, cannot manage other users' roles
 *   - author: create/edit own drafts, cannot publish (enforced in
 *     `src/hooks/enforcePublishRole.ts`) or delete
 */
export const Users: CollectionConfig = {
  slug: 'users',
  auth: true,
  admin: { useAsTitle: 'email', defaultColumns: ['email', 'role'] },
  access: {
    read: () => true,
    create: isAdmin,
    update: isAdmin,
    delete: isAdmin,
  },
  fields: [
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
