// The console's Payload instance.
//
// ARCHITECTURE.md's Platform DB note says: "A Payload instance will own
// platform `public` later, when the partner console (E4.4) needs an editing
// surface." This is that instance. It binds to `now_platform` and owns
// `public` there, exactly as the CMS owns `public` in each city database.
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
//   - the console's pages keep reading `engine.*` read-only, behind that auth
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
