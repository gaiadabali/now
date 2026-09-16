#!/usr/bin/env node
/**
 * Every route under `(site)/account` must refuse to serve when the account
 * surface cannot work (F141).
 *
 * The bug this guards against already reached production once. `/account/*`
 * was public on both cities with no SMTP configured, and registration did not
 * fail — it *succeeded wrongly*: created the row, hashed the password, told the
 * person to check an inbox nothing was sent to. The fix is `accountsEnabled()`
 * on every route, and the thing most likely to undo it is not someone deleting
 * the guard, it is someone adding a **new** route and not knowing it was
 * needed.
 *
 * So this is a lint rather than a test: a test covers the routes that exist, a
 * lint covers the ones that do not exist yet. Same reasoning as
 * `lint-site-literals.mjs`, which exists because "remember not to hardcode the
 * city name" is not a thing a person can be relied on to remember.
 */
import { readFileSync } from 'node:fs'
import { readdir } from 'node:fs/promises'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..', 'src', 'app', '(site)', 'account')

/** Files that render or handle a request. A `layout.tsx` would count too. */
const ROUTE_FILES = new Set(['page.tsx', 'route.ts', 'layout.tsx'])

async function walk(dir) {
  const found = []
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) found.push(...(await walk(full)))
    else if (ROUTE_FILES.has(entry.name)) found.push(full)
  }
  return found
}

const routes = await walk(root)
if (routes.length === 0) {
  console.error('[account-gate] found no routes under (site)/account — did the path move?')
  process.exit(1)
}

const ungated = routes.filter((file) => !readFileSync(file, 'utf8').includes('accountsEnabled()'))

if (ungated.length > 0) {
  console.error('[account-gate] these account routes do not call accountsEnabled():\n')
  for (const file of ungated) console.error('  ' + relative(join(here, '..'), file).replace(/\\/g, '/'))
  console.error(
    '\n  Every route under (site)/account must refuse to serve when mail is not\n' +
      '  configured — otherwise sign-up collects a real password for an account\n' +
      '  that can never be verified. See lib/reader.ts accountsEnabled() (F141).',
  )
  process.exit(1)
}

console.log(`✓ all ${routes.length} account routes gated on accountsEnabled()`)
