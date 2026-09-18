import type { CollectionConfig } from 'payload'

import { isAuthorOrAbove, isEditorOrAbove } from '../access'
import { GROUPS } from './groups'

/**
 * `authors` — public byline/profile, deliberately separate from `users`
 * (CMS login accounts). Legacy WordPress bylines don't all map to a real
 * login (E1.1: authors extracted from `wp_users`), and a byline like
 * "NOW! Editorial Team" is not a person who logs in. `articles.author` relates to
 * this collection, not to `users`.
 */
export const Authors: CollectionConfig = {
  slug: 'authors',
  admin: {
    group: GROUPS.editorial,
    useAsTitle: 'name',
    description: 'Bylines. One row per person who writes; each gets their own page on the site.',
  },
  access: {
    read: () => true,
    create: isAuthorOrAbove,
    update: isAuthorOrAbove,
    delete: isEditorOrAbove,
  },
  fields: [
    { name: 'name', type: 'text', required: true },
    { name: 'slug', type: 'text', required: true, unique: true, index: true },
    { name: 'bio', type: 'textarea' },
    { name: 'avatar', type: 'upload', relationTo: 'media' },
    { name: 'legacyWpUserId', label: 'Legacy WP user ID', type: 'number', index: true },
  ],
}
