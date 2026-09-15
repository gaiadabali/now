import type { CollectionConfig } from 'payload'

import { isAuthorOrAbove, isEditorOrAbove } from '../access'

/**
 * `media` — ARCHITECTURE.md §5 / §14.
 *
 * Payload's `upload: true` already manages `filename` (→ storage_key),
 * `mimeType`, `filesize`, `width`, `height` and thumbnail generation via
 * `sharp` — those are not re-declared as custom fields. `alt` and `credit`
 * are the two editorial fields ARCHITECTURE.md calls out explicitly.
 * Storage backend (Garage, S3-compatible) is wired in `payload.config.ts`
 * via `@payloadcms/storage-s3`, guarded so local dev without a Garage
 * bucket still boots (falls back to Payload's local-disk default).
 */
export const Media: CollectionConfig = {
  slug: 'media',
  admin: { useAsTitle: 'alt' },
  access: {
    read: () => true,
    create: isAuthorOrAbove,
    update: isAuthorOrAbove,
    delete: isEditorOrAbove,
  },
  upload: {
    imageSizes: [
      { name: 'thumbnail', width: 400, height: undefined, position: 'centre' },
      { name: 'card', width: 800, height: undefined, position: 'centre' },
      { name: 'hero', width: 1600, height: undefined, position: 'centre' },
    ],
    adminThumbnail: 'thumbnail',
    mimeTypes: ['image/*'],
  },
  fields: [
    {
      name: 'alt',
      type: 'text',
      required: true,
      admin: { description: 'Required — accessibility and E1.3 legacy alt-text preservation.' },
    },
    { name: 'credit', type: 'text' },
  ],
}
