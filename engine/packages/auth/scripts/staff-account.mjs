#!/usr/bin/env node
/**
 * Create or update a staff account in `now_platform.public.users`.
 *
 * **Why this has to exist.** Payload's "create the first user" screen is
 * gone: the city `users` collection sets `disableLocalStrategy`, and identity
 * moved to the platform table where this app's Payload cannot reach it
 * (docs/ADMIN-CONSOLIDATION.md Phase 1). That was the only supported way to
 * mint an account, so after the consolidation there was none at all — a fresh
 * deployment came up with a working `/team-editor` sign-in form and nothing
 * on earth that could get through it. DEPLOY.md said "seed one deliberately"
 * without saying how.
 *
 * It writes the SAME credential shape Payload's local strategy produces, by
 * calling `hashPassword` from this package rather than reimplementing it — so
 * a change to the PBKDF2 parameters cannot leave this script minting
 * credentials that `verifyPassword` then rejects.
 *
 *   node --experimental-strip-types scripts/staff-account.mjs \
 *     --email person@example.com --name "Their Name" \
 *     --editorial admin --commerce viewer
 *
 * Prints a generated password once. Pass `--password` only for a throwaway
 * dev account: an argument is visible in `ps` and in shell history, which a
 * generated one never is.
 *
 * Idempotent on email. Re-running resets the password and the roles, which is
 * also how you unlock an account that has locked itself out — `login_attempts`
 * goes back to zero.
 */

import crypto from 'node:crypto'
import process from 'node:process'

import pg from 'pg'

import { hashPassword } from '../src/password.ts'
import { COMMERCE_ROLES, EDITORIAL_ROLES, normaliseEmail } from '../src/identity.ts'

const { Client } = pg

function parseArgs(argv) {
  const args = {}
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i]
    if (!token.startsWith('--')) continue
    const key = token.slice(2)
    const next = argv[i + 1]
    if (next === undefined || next.startsWith('--')) {
      args[key] = true
    } else {
      args[key] = next
      i++
    }
  }
  return args
}

function die(message) {
  console.error(`\nerror: ${message}\n`)
  process.exit(1)
}

/**
 * 18 random bytes, base64url. Long enough that the 25k-iteration PBKDF2
 * behind it never has to carry the weight, and copy-pasteable without the
 * ambiguity a generated "memorable" password introduces.
 */
function generatePassword() {
  return crypto.randomBytes(18).toString('base64url')
}

const args = parseArgs(process.argv.slice(2))

if (args.help || !args.email) {
  console.log(
    [
      '',
      'Create or update a staff account in the platform identity store.',
      '',
      '  --email      <address>              required',
      '  --name       <display name>         optional',
      `  --editorial  <${EDITORIAL_ROLES.join('|')}>   default: none`,
      `  --commerce   <${COMMERCE_ROLES.join('|')}>   default: none`,
      '  --password   <value>                optional; generated when omitted',
      '',
      'Reads PLATFORM_DATABASE_URI from the environment.',
      '',
    ].join('\n'),
  )
  // `--help` is a request that succeeded; a missing --email is a usage error.
  process.exit(args.help ? 0 : 1)
}

const uri = process.env.PLATFORM_DATABASE_URI
if (!uri) die('PLATFORM_DATABASE_URI is not set. It must point at now_platform.')

const email = normaliseEmail(String(args.email))
const editorialRole = args.editorial ? String(args.editorial) : 'none'
const commerceRole = args.commerce ? String(args.commerce) : 'none'

if (!EDITORIAL_ROLES.includes(editorialRole)) {
  die(`--editorial must be one of: ${EDITORIAL_ROLES.join(', ')}`)
}
if (!COMMERCE_ROLES.includes(commerceRole)) {
  die(`--commerce must be one of: ${COMMERCE_ROLES.join(', ')}`)
}
// Both 'none' is a real state — a row that exists and can sign in nowhere —
// but it is almost never what someone typing this command meant.
if (editorialRole === 'none' && commerceRole === 'none') {
  die('both roles are "none", so this account could sign in and see nothing. Pass --editorial or --commerce.')
}

const password = args.password === undefined ? generatePassword() : String(args.password)
const generated = args.password === undefined

const client = new Client({ connectionString: uri })

try {
  await client.connect()
  const { hash, salt } = await hashPassword(password)

  const { rows } = await client.query(
    `INSERT INTO public.users
       (email, name, hash, salt, editorial_role, commerce_role,
        login_attempts, lock_until, updated_at, created_at)
     VALUES ($1, $2, $3, $4, $5, $6, 0, NULL, now(), now())
     ON CONFLICT (email) DO UPDATE
        SET name           = COALESCE(EXCLUDED.name, public.users.name),
            hash           = EXCLUDED.hash,
            salt           = EXCLUDED.salt,
            editorial_role = EXCLUDED.editorial_role,
            commerce_role  = EXCLUDED.commerce_role,
            -- Resetting the credential clears the lockout with it; otherwise
            -- the fix for "I am locked out" would still leave you locked out.
            login_attempts = 0,
            lock_until     = NULL,
            updated_at     = now()
     RETURNING id, (xmax = 0) AS created`,
    [email, args.name ? String(args.name) : null, hash, salt, editorialRole, commerceRole],
  )

  const row = rows[0]
  console.log(`\n${row.created ? 'Created' : 'Updated'} staff account #${row.id}`)
  console.log(`  email      ${email}`)
  console.log(`  editorial  ${editorialRole}`)
  console.log(`  commerce   ${commerceRole}`)
  if (generated) {
    console.log(`  password   ${password}`)
    console.log('\nThis is the only time that password is shown. Store it now.')
  }
  // The city shadow row is NOT written here. It is created by the sign-in
  // route on first use (`upsertShadowUser`), which is the one code path that
  // should own it — writing a second one here would be a second source of
  // truth for exactly the thing Phase 1 consolidated.
  console.log('\nSign in at <city>/team-editor to project the shadow row.\n')
} catch (error) {
  die(error?.message ?? String(error))
} finally {
  await client.end().catch(() => {})
}
