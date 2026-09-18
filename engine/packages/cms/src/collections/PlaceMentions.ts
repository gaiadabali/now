import type { CollectionConfig } from 'payload'

import { isAuthorOrAbove, isEditorOrAbove } from '../access'
import { GROUPS } from './groups'

/**
 * `place_mentions` — ARCHITECTURE.md §5 / §11.
 *
 * "Articles never contain partner links. They contain entity references."
 * This is the join row an editor (or, later, E2.3's extractor) creates
 * linking a span of article text to a place row; link rendering is
 * resolved at request time by engine-api from the current partnership,
 * never stored here.
 */
export const PlaceMentions: CollectionConfig = {
  slug: 'place-mentions',
  labels: { singular: 'Place mention', plural: 'Place mentions' },
  admin: {
    group: GROUPS.engine,
    useAsTitle: 'surfaceText',
    defaultColumns: ['article', 'place', 'surfaceText', 'role'],
  },
  access: {
    read: () => true,
    create: isAuthorOrAbove,
    update: isAuthorOrAbove,
    delete: isEditorOrAbove,
  },
  fields: [
    { name: 'article', type: 'relationship', relationTo: 'articles', required: true },
    { name: 'place', type: 'relationship', relationTo: 'places', required: true },
    {
      name: 'offset',
      type: 'number',
      min: 0,
      admin: { description: 'Character offset of the mention within the rendered article body.' },
    },
    { name: 'surfaceText', label: 'Surface text', type: 'text', required: true },
    {
      name: 'role',
      type: 'select',
      defaultValue: 'mentioned',
      options: ['mentioned', 'featured', 'reviewed'],
    },
  ],
}
