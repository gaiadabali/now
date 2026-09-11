// ONE Payload config, instantiated per city (ARCHITECTURE.md §3.5). The
// only thing that may differ between two deployments of this same image
// (e.g. one process per city) is the `DATABASE_URI` env var this file
// reads — see README.md. Zero site-name literals live in this file or
// anywhere under this package; that is mechanically checked by
// `npm run lint:site-literals`.

import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { postgresAdapter } from '@payloadcms/db-postgres'
import { lexicalEditor } from '@payloadcms/richtext-lexical'
import { s3Storage } from '@payloadcms/storage-s3'
import { buildConfig } from 'payload'
import sharp from 'sharp'

import { buildArticlesCollection } from '@/collections/Articles'
import { Authors } from '@/collections/Authors'
import { buildClassificationReviewsCollection } from '@/collections/ClassificationReviews'
import { Events } from '@/collections/Events'
import { Media } from '@/collections/Media'
import { buildPlacesCollection } from '@/collections/Places'
import { PlaceMentions } from '@/collections/PlaceMentions'
import { Users } from '@/collections/Users'
import { loadVocabulary } from '@/lib/vocabulary'

const filename = fileURLToPath(import.meta.url)
const dirname = path.dirname(filename)

// Fetched once at boot from the platform DB (read-only) — see
// src/lib/vocabulary.ts for the full "why" of this cross-database read.
// Top-level await is valid ESM and is Payload's documented pattern for
// async config setup (e.g. dynamic i18n imports); the config bundler
// (esbuild, via @payloadcms/next) supports it.
const vocabulary = await loadVocabulary()

const hasGarageCreds = Boolean(
  process.env.GARAGE_S3_ENDPOINT && process.env.GARAGE_ACCESS_KEY_ID && process.env.GARAGE_SECRET_ACCESS_KEY,
)

export default buildConfig({
  secret: process.env.PAYLOAD_SECRET ?? 'dev-only-insecure-secret-change-me',
  admin: {
    user: Users.slug,
    importMap: { baseDir: path.resolve(dirname, 'src') },
    meta: {
      titleSuffix: process.env.SITE_SLUG ? ` — NOW! CMS (${process.env.SITE_SLUG})` : ' — NOW! CMS',
    },
  },
  editor: lexicalEditor(),
  collections: [
    buildArticlesCollection(vocabulary),
    buildPlacesCollection(vocabulary),
    buildClassificationReviewsCollection(vocabulary),
    Events,
    PlaceMentions,
    Media,
    Authors,
    Users,
  ],
  // db binds to exactly one database, per instance — this is the ONLY
  // per-city knob (ARCHITECTURE.md §3.5 point 4). `push` is disabled in
  // every environment (not just production) so that `public` schema
  // changes always go through a reviewable, named migration file — the
  // same discipline Alembic enforces on the `engine` side, just via
  // Payload's own migration runner instead of Alembic (Alembic must never
  // touch `public`; this is Payload's own tooling shaping the schema it
  // owns).
  db: postgresAdapter({
    pool: { connectionString: process.env.DATABASE_URI },
    push: false,
    migrationDir: path.resolve(dirname, 'src/migrations'),
  }),
  sharp,
  typescript: {
    outputFile: path.resolve(dirname, 'payload-types.ts'),
  },
  plugins: hasGarageCreds
    ? [
        s3Storage({
          collections: { media: true },
          bucket: process.env.GARAGE_MEDIA_BUCKET ?? 'now-media',
          config: {
            endpoint: process.env.GARAGE_S3_ENDPOINT,
            region: process.env.GARAGE_S3_REGION ?? 'garage',
            credentials: {
              accessKeyId: process.env.GARAGE_ACCESS_KEY_ID ?? '',
              secretAccessKey: process.env.GARAGE_SECRET_ACCESS_KEY ?? '',
            },
            forcePathStyle: true,
          },
        }),
      ]
    : [],
})
