import type { CollectionConfig } from 'payload'

import { isAuthorOrAbove, isEditorOrAbove } from '../access'
import { GROUPS } from './groups'

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
  admin: {
    group: GROUPS.editorial,
    useAsTitle: 'alt',
    description:
      'Pictures. These are still served from the old WordPress site, so uploading a new one '
      + 'does not work yet — existing pictures are fine to use (docs/DEPLOY.md §6).',
  },
  access: {
    read: () => true,
    create: isAuthorOrAbove,
    update: isAuthorOrAbove,
    delete: isEditorOrAbove,
  },
  upload: {
    // The files are NOT on this host. E1.3 (mirroring ~9 GB of
    // wp-content/uploads into Garage) has not run, so every row here points
    // at an asset that still lives on the legacy WordPress origin — which is
    // exactly what `media.url` holds and what next.config's remotePatterns
    // already allow.
    //
    // Without this, Payload assumes it owns the bytes: it generates
    // `/api/media/file/<filename>` for every image, next/image proxies that
    // through /_next/image, and each one 500s on a file that was never
    // there. `disableLocalStorage` stops Payload claiming the files and
    // leaves the stored URL intact.
    //
    // This comes out in the same change that lands the Garage mirror.
    disableLocalStorage: true,
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
