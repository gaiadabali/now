#!/usr/bin/env node
/**
 * S5.1 — asserts the validators the platform console reuses from the reader.
 *
 * `lib/site.ts` exports `navFrom`, `brandTokensFrom` and `railsFrom` so the
 * console's write path (`team-editor/platform/sites/[slug]/actions.ts`)
 * validates a save with the exact function `getSiteConfig()` runs a read
 * through — the ticket's own words for the alternative: a console that keeps
 * a second, hand-written copy of the same shape check can drift from it, and
 * the drift is invisible until an editor saves something the copy accepted
 * and the real one rejects. This is the check that the two never had the
 * chance to disagree, because there is only one.
 *
 * **Why a script and not `test/*.test.ts`.** `lib/site.ts` imports
 * `@/lib/db` via the `@/*` path alias `tsconfig.json` declares for Next's
 * bundler — plain `node --test` has no bundler and does not resolve it, so a
 * bare `import '../src/lib/site.ts'` fails before this file's exports are
 * even reached. `lib/db.ts` also imports `server-only`, which throws
 * unconditionally unless the `react-server` export condition is active
 * (Next sets it when bundling Server Components; a plain Node process does
 * not). `scripts/lib/alias-loader.mjs` resolves the first; `--conditions
 * react-server` supplies the second. Together they reproduce just enough of
 * what Next does to load the real module rather than a stand-in for it —
 * the same reasoning as `packages/cms/scripts/verify-article-admin.mjs`
 * running through `payload run` instead of `node --test`, for a different
 * blocker (`Articles.ts` imports a directory, which plain Node ESM also does
 * not resolve).
 *
 * `loadRegistry`/`getSiteConfig` are NOT exercised here — they open a real
 * pool via `db()`, and this script's whole point is to run with no database
 * and no Next process at all. The database-backed half of S5.1 (a console
 * edit reaching the reader within the TTL) is verified live, against the
 * real stack, and reported by hand rather than scripted — see the ticket.
 *
 * Run with:
 *   node --conditions react-server --experimental-strip-types scripts/verify-site-config.mjs
 */
import { register } from 'node:module'

register('./lib/alias-loader.mjs', import.meta.url)

const { brandTokensFrom, loadSiteConfigFile, navFrom, railsFrom } = await import('../src/lib/site.ts')

const failures = []
function check(ok, label, detail = '') {
  console.log(`[verify] ${ok ? 'PASS' : 'FAIL'} — ${label}${detail ? ` :: ${detail}` : ''}`)
  if (!ok) failures.push(label)
}
function eq(a, b, label) {
  check(JSON.stringify(a) === JSON.stringify(b), label, `got ${JSON.stringify(a)}`)
}

/* --------------------------------------------------------------- navFrom */

eq(
  navFrom([
    { label: 'Dining', href: '/dining' },
    { label: 'Stay', href: '/stay' },
  ]),
  [
    { label: 'Dining', href: '/dining' },
    { label: 'Stay', href: '/stay' },
  ],
  'a well-formed nav is accepted, in order',
)

// `{}` is the column default on every ungoverned row (`sites.nav jsonb NOT
// NULL DEFAULT '{}'::jsonb`) — the one case this whole ticket exists to get
// right. Rejecting it, not coercing it to zero items, is what makes "falling
// back to the file" possible instead of "renders with no navigation".
eq(navFrom({}), null, 'the ungoverned default {} is rejected, not read as zero items')

eq(navFrom([]), null, 'an empty array is rejected — S5.1: never let a save produce this from a form')

eq(
  navFrom([{ label: 'Dining', href: '/dining' }, { label: '', href: '/stay' }]),
  null,
  'one item with an empty label rejects the WHOLE nav, not just that item',
)
eq(
  navFrom([{ label: 'Dining', href: '/dining' }, { label: 'Stay', href: '' }]),
  null,
  'one item with an empty href rejects the whole nav',
)
eq(navFrom([{ label: 'Dining' }]), null, 'an item missing href entirely is rejected')
eq(navFrom('not an array'), null, 'a non-array value is rejected')
eq(navFrom(null), null, 'null is rejected')

/* ------------------------------------------------------------- railsFrom */

eq(railsFrom([{ key: 'guides' }, { key: 'events', label: 'What’s On' }]), [{ key: 'guides' }, { key: 'events', label: 'What’s On' }], 'a well-formed rail order is accepted')
eq(railsFrom({}), null, 'the ungoverned default {} is rejected')
eq(railsFrom([]), null, 'an empty array is rejected by the validator (the console still permits SAVING one — see actions.ts)')
eq(railsFrom([{ key: 'guides' }, { key: '' }]), null, 'one rail with an empty key rejects the whole order')
eq(railsFrom([{ label: 'no key at all' }]), null, 'a rail with no key field is rejected')

/* -------------------------------------------------------- brandTokensFrom */

eq(brandTokensFrom({ logo: '/brand/x.svg', favicon: '' }), { logo: '/brand/x.svg' }, 'only non-empty string fields survive; an empty string is treated as absent, not as "set to empty"')
eq(brandTokensFrom({}), {}, 'the ungoverned default {} yields nothing governed')
eq(brandTokensFrom([]), {}, 'an array (wrong shape for this column) yields nothing governed')
eq(brandTokensFrom(null), {}, 'null yields nothing governed')
eq(brandTokensFrom({ logo: 42 }), {}, 'a non-string value for a recognised key is dropped, not coerced')
eq(
  brandTokensFrom({ logo: '/a.svg', logoAlt: 'Alt', favicon: '/f.png', appleIcon: '/a.png', extra: 'ignored' }),
  { logo: '/a.svg', logoAlt: 'Alt', favicon: '/f.png', appleIcon: '/a.png' },
  'all four recognised keys pass through; an unrecognised key is dropped',
)

/* --------------------------------------------------- loadSiteConfigFile */
// Reads real files in this checkout rather than fixtures, the same way
// verify-article-slug.mjs drives Payload's real Local API rather than a
// mock of it — a fixture cannot be wrong about its own shape, and the file
// this reads is production content.

const siteSlugs = process.env.NOW_VERIFY_SITE_SLUGS?.split(',').filter(Boolean) ?? []
if (siteSlugs.length === 0) {
  console.log('[verify] SKIP — set NOW_VERIFY_SITE_SLUGS=<slug>[,<slug>] to check loadSiteConfigFile against real files')
} else {
  for (const slug of siteSlugs) {
    try {
      const config = await loadSiteConfigFile(slug)
      check(Array.isArray(config.nav) && config.nav.length > 0, `${slug}: site.config.json has a non-empty nav`, `${config.nav?.length} item(s)`)
      check(typeof config.brand?.logo === 'string', `${slug}: site.config.json declares a brand.logo`)
    } catch (err) {
      check(false, `${slug}: loadSiteConfigFile should have read a real file`, String(err))
    }
  }
}

// A slug with no config file (this checkout's `test/site/` has none) must
// reject with the read error, not throw something this script cannot tell
// apart from "the file was empty" or return a fabricated default — the edit
// page's whole "no config file for this site" message depends on this being
// a real, catchable failure and not a silent {}.
try {
  await loadSiteConfigFile('__now_verify_missing_site__')
  check(false, 'loadSiteConfigFile rejects a slug with no config file')
} catch {
  check(true, 'loadSiteConfigFile rejects a slug with no config file')
}

/* ------------------------------ the two sources, independently optional */

/**
 * `getSiteConfig()` has two sources and must survive losing either one.
 *
 * S1.3 shipped the registry read with the baked file underneath it and got one
 * of the two failure modes right: a registry that cannot be reached logs and
 * degrades to the file. The other was wrong and nobody noticed, because both
 * deployed cities bake a file in — `loadFile()` was awaited OUTSIDE the try,
 * so an absent `site.config.json` threw uncaught and, on a `force-dynamic`
 * root layout, returned 500 on every route including the ones that touch no
 * database at all.
 *
 * S5.1 is what turned that from theoretical into reachable: a console that can
 * register and govern a city can produce a city with a registry row and no
 * file in the repo, which is exactly what ARCHITECTURE.md §3.5's "adding a
 * city is one command plus config" ought to allow.
 *
 * All four combinations are pinned below. Needs a reachable platform database
 * and skips without one, the same way the real-file checks above do.
 */
const platformUrl = process.env.PLATFORM_DATABASE_URL ?? process.env.PLATFORM_DATABASE_URI
const matrixSlug = process.env.NOW_VERIFY_CONFIG_SLUG ?? siteSlugs[0]

if (!platformUrl || !matrixSlug) {
  console.log(
    '[verify] SKIP — set PLATFORM_DATABASE_URL and NOW_VERIFY_SITE_SLUGS (or ' +
      'NOW_VERIFY_CONFIG_SLUG) to check the file/registry fallback matrix',
  )
} else {
  const { execFileSync } = await import('node:child_process')
  const { mkdtempSync } = await import('node:fs')
  const { tmpdir } = await import('node:os')
  const { fileURLToPath } = await import('node:url')
  const { join } = await import('node:path')

  // A directory that exists and contains no <slug>/site/site.config.json, so
  // the file read fails the way a missing bake would rather than the way a
  // missing mount would.
  const emptyRoot = mkdtempSync(join(tmpdir(), 'now-verify-noconfig-'))
  const repoRoot = fileURLToPath(new URL('../../../../', import.meta.url))
  const probe = fileURLToPath(new URL('./lib/site-config-probe.mjs', import.meta.url))
  // Port 1 refuses immediately, so "unreachable" costs no timeout.
  const deadUrl = 'postgresql://now:nope@127.0.0.1:1/now_platform'

  const run = (root, url) => {
    const args = ['--conditions', 'react-server', '--experimental-strip-types', probe]
    const opts = {
      env: { ...process.env, NOW_REPO_ROOT: root, SITE_SLUG: matrixSlug, PLATFORM_DATABASE_URL: url },
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }
    // The probe exits 1 on the case that is SUPPOSED to throw, so a non-zero
    // exit is a result to parse rather than an error to report.
    let out
    try {
      out = execFileSync(process.execPath, args, opts)
    } catch (err) {
      out = String(err.stdout ?? '')
    }
    const last = out.trim().split('\n').pop() ?? ''
    try {
      return JSON.parse(last)
    } catch {
      return { ok: false, error: `probe produced no JSON: ${last.slice(0, 120)}` }
    }
  }

  const both = run(repoRoot, platformUrl)
  check(both.ok && both.nav > 0, 'file + registry: serves a full config', JSON.stringify(both))

  const registryOnly = run(emptyRoot, platformUrl)
  check(
    registryOnly.ok && registryOnly.nav > 0,
    'registry only, NO config file: serves instead of 500ing every route',
    JSON.stringify(registryOnly),
  )

  const fileOnly = run(repoRoot, deadUrl)
  check(
    fileOnly.ok && fileOnly.nav > 0 && fileOnly.tagline !== '',
    'file only, registry unreachable: S1.3 behaviour still holds',
    JSON.stringify(fileOnly),
  )

  const neither = run(emptyRoot, deadUrl)
  check(
    !neither.ok && /No configuration for site/.test(neither.error ?? ''),
    'neither source: fails loudly and names what is missing',
    JSON.stringify(neither),
  )
}

if (failures.length > 0) {
  console.error(`\n[verify] FAILED — ${failures.length} check(s): ${failures.join('; ')}`)
  process.exit(1)
}
console.log('\n[verify] OK — the console validates a write with the exact functions that decide what a read does with it.')
process.exit(0)
