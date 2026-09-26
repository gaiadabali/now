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
import { Editions } from './src/collections/Editions'
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
      // `NavPlatform` is the same shape for the same reason — `engine.sites`
      // lives in the platform database too.
      //
      // Order is deliberate: Front page and Curation sit above Commerce,
      // Staff and Platform because far more people curate or review than
      // sell than administer accounts or the site registry. Each component
      // decides for itself whether to render, against the role dimension it
      // actually cares about.
      afterNavLinks: [
        '/components/nav/NavFrontPage#NavFrontPage',
        '/components/nav/NavReview#NavReview',
        '/components/nav/NavConsole#NavConsole',
        '/components/nav/StaffLink#StaffLink',
        '/components/nav/NavPlatform#NavPlatform',
      ],
      // The account menu Payload does not have. Its avatar is a plain link
      // to the profile page, so there was nowhere to put "sign out" except
      // an unlabelled arrow at the foot of the nav. `actions` renders into
      // the app header beside the avatar, which is where people look.
      actions: ['/components/nav/AccountMenu#AccountMenu'],
      // S3.1 — one chrome for all of `/team-editor`.
      //
      // Classification, commerce and staff used to be literal Next routes
      // under `(payload)/team-editor/**`, OUTSIDE Payload's own catch-all
      // (`team-editor/[[...segments]]/page.tsx`). Next resolves a literal
      // route before a catch-all at the same level, so those routes silently
      // shadowed Payload's router for every URL under them — which is why
      // they never had Payload's sidebar: each brought its own masthead, and
      // the only way from one to another (or back to Payload's own
      // dashboard) was a small `editor` badge in a corner.
      //
      // Registering them here instead makes Payload's catch-all the one and
      // only router for the whole admin. `getCustomViewByRoute`
      // (@payloadcms/next) matches `path` against the URL with
      // `path-to-regexp` and renders the `Component` inside the SAME
      // `DefaultTemplate` every collection screen uses — sidebar included —
      // so removing the bespoke route files (done) is what actually fixes
      // the complaint; this config change is what makes removing them safe.
      //
      // ONE VIEW PER AREA, NOT ONE PER SCREEN. `path` is matched with
      // `exact` unset, i.e. as a PREFIX — `/classification` also matches
      // `/classification/123` and `/classification/review/cluster` — and
      // each `Component` below does its own routing over the leftover
      // segments, the same decision a Next.js folder tree used to make for
      // free. Two reasons this is one registration and not four or five:
      //
      //   1. Payload picks the FIRST entry in this object whose `path`
      //      matches, and matching is by pattern, not by specificity —
      //      unlike Next's file router, there is no "the literal segment
      //      wins over the dynamic one" rule. `/classification/review` and a
      //      hypothetical `/classification/:id` are both two segments, so a
      //      dynamic entry registered first would swallow `review` as an id
      //      with nothing to stop it. Doing the routing inside one component
      //      turns that into an ordinary `if`-chain, checked once, next to
      //      the code it dispatches to — see `ClassificationView.tsx`.
      //   2. `meta` is per registered path, and every screen inside an area
      //      already shared one browser-tab title (the masthead layouts this
      //      ticket removes each set exactly one `metadata.title` for their
      //      whole subtree). One view, one `meta.title`, is what the reader
      //      already saw — not a regression, just no longer implemented with
      //      a Next.js layout.
      //
      // THE PATHS BELOW ARE NOT IMPORTED FROM `paths.ts` IN THOSE FOLDERS.
      // They could not be: `paths.ts` lives in `apps/web`, and this package
      // must never import app code (§1 — it is what keeps the city-DB and
      // platform-DB boundary a compile-time fact rather than a convention).
      // So `/classification`, `/commerce` and `/staff` are hand-written here
      // and have to agree with `CLASSIFY_ROOT`, `CONSOLE_ROOT` and
      // `STAFF_ROOT` (minus the `/team-editor` prefix, which is `routes.admin`
      // below) by inspection — the same two-places-must-agree shape
      // `consoleHref`'s own comment already names.
      //
      // THE COMPONENT PATHS ARE APP-LOCAL, DELIBERATELY NOT UNDER THIS
      // PACKAGE'S `src`. A `@/…` specifier does not start with `.` or `/`, so
      // Payload's import-map generator treats it as a bare package/alias
      // import (`addPayloadComponentToImportMap.js`: "Tsconfig alias or
      // package import") and writes it into the generated map VERBATIM,
      // rather than resolving it against `admin.importMap.baseDir` (this
      // package's `src`) the way `/components/...` above is. The generated
      // map is a file INSIDE `apps/web`
      // (`app/(payload)/team-editor/importMap.js`), so that verbatim `@/…`
      // specifier is resolved by the APP's own tsconfig (`@/*` → `apps/web/
      // src/*`) when the app's bundler builds it — never by this package's.
      // That is what lets a Payload view live in this shared CMS package
      // while its Component is the app's own code, reading `@/lib/auth` and
      // `@/lib/queries` the way every other admin page in `apps/web` does,
      // without this package importing a single line of the app or the
      // app's business logic moving into this package. Confirmed against
      // `node_modules/payload/dist/bin/generateImportMap/utilities/
      // addPayloadComponentToImportMap.js` before relying on it — this was
      // the open question S3.1 was scoped to answer before committing to
      // this approach over a hand-built shared masthead.
      views: {
        // Edition 2, WS3 — the desk home (`app/(payload)/team-editor/desk/
        // DeskHome.tsx`). `dashboard` is a RESERVED key, not part of the
        // path-matched set below: `@payloadcms/next`'s `DashboardView`
        // (`views/Dashboard/index.js`) reads
        // `config.admin?.components?.views?.dashboard?.Component` directly
        // and falls back to its own `DefaultDashboard` when it is unset —
        // it is not reached through `getCustomViewByRoute`'s pattern
        // matching at all, and `getRouteData`'s `segments.length === 0`
        // branch (the admin root) hardcodes `DashboardView` regardless of
        // what is registered under `path` here. So this entry cannot
        // collide with, shadow, or be shadowed by any `path`-matched view
        // below — "one registration per area, first match wins" (this
        // block's own note further down) is a rule about THOSE, not this.
        // No `AdminViewFrame` needed either: see `DeskHome.tsx`'s header for
        // why the admin root already gets Payload's template regardless.
        dashboard: {
          Component: '@/app/(payload)/team-editor/desk/DeskHome#DeskHome',
        },
        classification: {
          Component: '@/app/(payload)/team-editor/classification/ClassificationView#ClassificationView',
          path: '/classification',
          meta: {
            title: 'Classification',
            description: 'What the engine decided about an article, and how sure it was',
          },
        },
        // Plan P1.6 — the place desk: the place catalogue's review queue in
        // evidence order, and one place's evidence and decisions. Reviewer-
        // gated in the view and in every action; see
        // `app/(payload)/team-editor/place-desk/PlaceDeskView.tsx`.
        placeDesk: {
          Component: '@/app/(payload)/team-editor/place-desk/PlaceDeskView#PlaceDeskView',
          path: '/place-desk',
          meta: {
            title: 'Place desk',
            description: 'Approve, merge or junk the places the magazine has named',
          },
        },
        commerce: {
          Component: '@/app/(payload)/team-editor/commerce/CommerceView#CommerceView',
          path: '/commerce',
          meta: { title: 'Console', description: 'Partner and campaign management' },
        },
        // No sub-routes, so `exact: true` — nothing under `/staff/*` should
        // ever match this, and there is nothing there to dispatch to.
        staff: {
          Component: '@/app/(payload)/team-editor/staff/StaffView#StaffView',
          path: '/staff',
          exact: true,
          meta: { title: 'Staff', description: 'Staff accounts and roles' },
        },
        // The platform console (S5.1). Registered here for the same reason
        // as the three above and found the same way: it shipped as literal
        // `page.tsx` routes, which shadow Payload's catch-all, so it was the
        // one screen with a sidebar link and no sidebar. See
        // `app/(payload)/team-editor/platform/PlatformView.tsx`.
        // Edition 2, WS3. Appended after the four areas above rather than
        // interleaved with them: `/front-page` shares no path prefix with
        // `/classification`, `/commerce`, `/staff` or `/platform`, so there
        // is no first-match-wins ordering hazard to reason about against any
        // of them — this note only needs to say that placement here is safe,
        // not that it was chosen carefully among competing prefixes the way
        // a genuinely overlapping pair would need. No sub-routes, so
        // `exact: true`, same as `staff` above.
        frontPage: {
          Component: '@/app/(payload)/team-editor/front-page/FrontPageView#FrontPageView',
          path: '/front-page',
          exact: true,
          meta: { title: 'Front page', description: 'What leads the home page, and in what order' },
        },
        platform: {
          Component: '@/app/(payload)/team-editor/platform/PlatformView#PlatformView',
          path: '/platform',
          meta: { title: 'Platform', description: 'The sites registry and what readers see' },
        },
      },
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
  // ORDER IS THE SIDEBAR ORDER, and now also the group order (S3.2).
  //
  // Payload renders sidebar groups in the order it first encounters them, so
  // this list decides both. Editorial comes first because it is the daily
  // work; Settings last because it is a read-only mirror nobody edits here.
  // Within Editorial, Articles is first for the same reason.
  //
  // The previous order interleaved them — Articles, Places, Classification
  // reviews, Events, Place mentions, Media, Authors, Users — which with
  // grouping switched on would have produced Editorial, Places, Engine,
  // Editorial again. Groups are not re-entrant.
  collections: [
    buildArticlesCollection(vocabulary), // ── Editorial
    Editions,
    Events,
    Media,
    Authors,
    buildPlacesCollection(vocabulary), // ── Places
    buildClassificationReviewsCollection(vocabulary), // ── Engine
    PlaceMentions,
    Users, // ── Settings
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
  // ALWAYS REGISTERED, switched off by `enabled` rather than by its absence.
  //
  // This used to be `hasGarageCreds ? [s3Storage(...)] : []`, and that shape
  // took the production admin down on 2026-09-17. The plugin contributes a
  // client component, `@payloadcms/storage-s3/client#S3ClientUploadHandler`,
  // which Payload resolves through the generated `importMap.js` — and the
  // importMap is generated at BUILD time, in an environment that has no Garage
  // credentials. Registering the plugin conditionally on a RUN-time value
  // therefore produced a build whose manifest did not contain the component
  // the running config asked for. Payload logs `getFromImportMap:
  // PayloadComponent not found in importMap` and renders NOTHING: every route
  // under /team-editor, the sign-in screen included, served valid HTML with an
  // empty Suspense boundary inside it. No error page, no failed request, and a
  // passing health check.
  //
  // `enabled: false` keeps the plugin in the config — so its component is in
  // the importMap of every build — while leaving it inert. The credentials
  // then decide behaviour, not the shape of the manifest, and supplying them
  // at run time can no longer disagree with what was baked at build time.
  plugins: [
    s3Storage({
      enabled: hasGarageCreds,
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
  ],
})
