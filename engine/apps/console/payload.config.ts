// The Payload instance that owns `now_platform.public`.
//
// ARCHITECTURE.md's Platform DB note says: "A Payload instance will own
// platform `public` later, when the partner console (E4.4) needs an editing
// surface." This is that instance. It binds to `now_platform` and owns
// `public` there, exactly as the CMS owns `public` in each city database.
//
// THERE IS NO CONSOLE ANY MORE, AND THIS IS STILL HERE ON PURPOSE.
// The partner pages moved to `/team-editor/commerce` and this package's
// admin UI is gone (docs/ADMIN-CONSOLIDATION.md Phases 3–4). What did NOT
// move is schema ownership: `public.users` is the staff identity store the
// whole admin authenticates against, and `src/migrations/` is the only
// record of how that table came to be. Deleting this package would delete
// the migration history for the one table every sign-in reads.
//
// So it is no longer an application — it is a migration home with a config
// attached. `npm run migrate -w @now-engine/console` is what it is for.
// Accounts are created with `npm run staff-account -w @now/auth`, not here.
//
// WHAT IT OWNS TODAY: `users`, and nothing else.
//
// The commerce tables (`orgs`, `partnerships`, `campaigns`, `placements`)
// deliberately stay in `now_platform.engine`, Alembic-owned, and this config
// does not model them. That is not an oversight — `engine.partnerships` is
// read **on the request path** by `now_link_resolver`, which is what makes
// `rel="sponsored"` structurally unomittable (§11, E4.2). Moving those tables
// into `public` so Payload could own them would break link resolution, the
// loader, and the CMS's Places collection in the same commit as an auth
// change. It is a deliberate migration with its own blast radius, and it
// belongs in its own change.
//
// So the split right now is:
//   - Payload owns `public.users` -> real sessions, roles, password reset
//   - the commerce pages under /team-editor keep reading `engine.*` read-only,
//     behind that auth
//
// Adding an editing surface later is then additive: model a collection, write
// the Payload migration that moves the table into `public`, and repoint the
// Python consumers in the same change.

import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { postgresAdapter } from '@payloadcms/db-postgres'
import { lexicalEditor } from '@payloadcms/richtext-lexical'
import { buildConfig } from 'payload'
import sharp from 'sharp'

import { Users } from '@/collections/Users'

const filename = fileURLToPath(import.meta.url)
const dirname = path.dirname(filename)

export default buildConfig({
  admin: {
    user: Users.slug,
    meta: {
      titleSuffix: '— NOW! Console',
    },
  },
  collections: [Users],
  editor: lexicalEditor(),
  secret: process.env.PAYLOAD_SECRET || '',
  // Binds to the PLATFORM database. Unlike the CMS this is not a per-city
  // knob — there is exactly one platform database and one console.
  //
  // `push: false` in every environment, matching the CMS: schema changes go
  // through a reviewable, named migration file rather than being inferred at
  // boot. Alembic owns `engine` here and must never touch `public`; this is
  // Payload's own tooling shaping the schema it owns.
  db: postgresAdapter({
    pool: { connectionString: process.env.DATABASE_URI },
    push: false,
    migrationDir: path.resolve(dirname, 'src/migrations'),
  }),
  sharp,
  typescript: {
    outputFile: path.resolve(dirname, 'payload-types.ts'),
  },
})
