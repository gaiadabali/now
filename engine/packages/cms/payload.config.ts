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

import { buildArticlesCollection } from './src/collections/Articles'
import { Authors } from './src/collections/Authors'
import { buildClassificationReviewsCollection } from './src/collections/ClassificationReviews'
import { Events } from './src/collections/Events'
import { Media } from './src/collections/Media'
import { buildPlacesCollection } from './src/collections/Places'
import { PlaceMentions } from './src/collections/PlaceMentions'
import { Users } from './src/collections/Users'
import { loadSiteBrand } from './src/lib/siteBrand'
import { loadVocabulary } from './src/lib/vocabulary'

const filename = fileURLToPath(import.meta.url)
const dirname = path.dirname(filename)

// Fetched once at boot from the platform DB (read-only) — see
// src/lib/vocabulary.ts for the full "why" of this cross-database read.
// Top-level await is valid ESM and is Payload's documented pattern for
// async config setup (e.g. dynamic i18n imports); the config bundler
// (esbuild, via @payloadcms/next) supports it.
const vocabulary = await loadVocabulary()

// Read at module load, alongside the vocabulary above and for the same
// reason: `admin.meta` is a plain object Payload sanitises once at boot, so
// a value that arrives per-request is too late. Reading a JSON file that
// the image bakes in costs nothing and cannot fail the boot — see
// src/lib/siteBrand.ts.
const brand = await loadSiteBrand()

const hasGarageCreds = Boolean(
  process.env.GARAGE_S3_ENDPOINT && process.env.GARAGE_ACCESS_KEY_ID && process.env.GARAGE_SECRET_ACCESS_KEY,
)

export default buildConfig({
  secret: process.env.PAYLOAD_SECRET ?? 'dev-only-insecure-secret-change-me',
  admin: {
    user: Users.slug,
    importMap: { baseDir: path.resolve(dirname, 'src') },
    meta: {
      titleSuffix: process.env.SITE_SLUG ? ` — NOW! (${process.env.SITE_SLUG})` : ' — NOW!',
      // The city's own mark on the admin tab.
      //
      // It has to be set HERE and not in the route group's layout. Payload's
      // catch-all page exports its own `generateMetadata`, and Next lets a
      // page's metadata win over its layout's for the same key — so a
      // favicon declared upstairs is silently replaced by Payload's on every
      // admin screen. `admin.meta` is the hook that feeds the generator
      // itself, which is the only place upstream of that.
      //
      // Left unset when the config is unreadable, so Payload falls back to
      // its own mark rather than to a broken image.
      ...(brand?.icon ? { icons: [{ rel: 'icon', url: brand.icon }] } : {}),
    },
    // The admin wears the client's brand, not Payload's.
    //
    // Both cities run this same config, so the marks cannot be named here;
    // the components read them from the city's own `site.config.json` at
    // render time (src/lib/siteBrand.ts), which keeps §3.5 intact — the
    // image stays city-agnostic and SITE_SLUG still decides everything.
    //
    // Paths, not imports: Payload resolves `admin.components` through the
    // generated import map so the client bundle can reach them. A leading
    // `/` means "relative to `admin.importMap.baseDir`", which is this
    // package's `src`; the generator rewrites it into a path relative to
    // whichever app owns the map. There is exactly one of those —
    // `apps/web/src/app/(payload)/team-editor/importMap.js` — so run
    // `npm run generate:importmap -w @now-engine/web` after touching this.
    components: {
      graphics: {
        Icon: '/components/graphics/SiteIcon#SiteIcon',
        Logo: '/components/graphics/SiteLogo#SiteLogo',
      },
      beforeNavLinks: ['/components/nav/NavMasthead#NavMasthead'],
      // Both of the surfaces Payload's nav will never list on its own. Its
      // nav enumerates COLLECTIONS, and neither of these is one: the commerce
      // console and the staff admin are plain Next pages reading
      // `now_platform` over SQL, which this Payload instance cannot reach.
      // Without a link here they are typed-URL-only — survivable for the
      // console, self-defeating for the one surface an admin needs in order
      // to onboard anybody.
      //
      // Order is deliberate: Commerce sits above Staff because far more
      // people have a commerce role than an editorial admin one. Each
      // component decides for itself whether to render, against the role
      // dimension it actually cares about.
      afterNavLinks: [
        '/components/nav/NavConsole#NavConsole',
        '/components/nav/StaffLink#StaffLink',
      ],
      // The account menu Payload does not have. Its avatar is a plain link
      // to the profile page, so there was nowhere to put "sign out" except
      // an unlabelled arrow at the foot of the nav. `actions` renders into
      // the app header beside the avatar, which is where people look.
      actions: ['/components/nav/AccountMenu#AccountMenu'],
    },
    // Payload's default account avatar is a GRAVATAR: it hashes the signed-in
    // email and fetches an image from gravatar.com on every admin page. For
    // staff who have no Gravatar — all of them — that is a third-party
    // request carrying a hash of their email, to render a grey silhouette.
    // A monogram costs nothing and looks like the brand.
    avatar: { Component: '/components/graphics/StaffAvatar#StaffAvatar' },
    // The sidebar carried no brand and ended in ~600px of nothing. Payload
    // gives both ends a slot; it just ships them empty.
    //   beforeNavLinks — the city masthead, so the surface an editor looks at
    //     all day says which city they are about to publish into.
    //   afterNavLinks  — who is signed in, their editorial role, and the way
    //     out. Sign-out previously hid inside the avatar menu.
    // Slots rather than a `Nav` override, so Payload can keep changing the
    // nav's internals without taking these with it.
  },
  // The admin is served BY THE READER APP, under the city's own hostname
  // (docs/ADMIN-CONSOLIDATION.md Phase 2): <city>.gaiada.com/team-editor. The
  // literal hostname was here until this file's own lint caught it.
  // It is no longer a separate deployment on a separate hostname, so this
  // route is what six hostnames collapsing to two actually rests on.
  //
  // Payload derives every admin URL it emits — login redirects, the logout
  // link, "create first user" — from this value. Changing it here and not in
  // the route folder (or the reverse) produces an admin that renders once and
  // then 404s the moment it navigates.
  routes: {
    admin: '/team-editor',
  },
  // The client's admin should not be advertising the CMS vendor. Payload
  // puts "Payload Settings" above the language and theme controls on the
  // account screen — the one string in the whole UI that names the product
  // rather than describing what it does. Overriding the key is the supported
  // way; patching the package is not.
  i18n: {
    translations: {
      en: { general: { payloadSettings: 'Editor settings' } },
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
