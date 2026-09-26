#!/usr/bin/env node
/**
 * P0.3 — asserts the gates every Phase 1-6 route/action is expected to call.
 *
 * `lib/modules.ts` exports `moduleEnabled()`, `requireModule()` (server
 * components/route handlers — 404 via `notFound()`, mirroring
 * `accountsEnabled()` in every `(site)/account` route, F141) and
 * `requireModuleForAction()` (server actions — returns `{ ok: false,
 * message }` instead of throwing, matching `PlatformActionResult`). This is
 * the check that all three agree with each other and with `lib/site.ts`'s
 * `modulesFrom()` — the same function `getSiteConfig()` runs the registry
 * column through.
 *
 * **Why a script and not `test/*.test.ts`.** Same reasoning as
 * `scripts/verify-site-config.mjs`: `lib/modules.ts` imports `lib/site.ts`
 * (`@/lib/site`), which imports `@/lib/db` — the `@/*` alias only Next's
 * bundler resolves. `--conditions react-server` supplies the condition
 * `lib/db.ts`'s `server-only` import needs. `test/modules.test.ts` covers
 * the one part of this (`lib/moduleNames.ts`) that needs neither.
 *
 * `lib/modules.ts` also imports `next/navigation` for `notFound()`, which
 * this script cannot load for real at all — see `scripts/lib/
 * stub-next-navigation.mjs` for why (the short version: `next/navigation`
 * needs the CLIENT react graph, `server-only` needs the react-server
 * CONDITION, and no single Node process gets both at once outside a real
 * Next build). `scripts/lib/module-flags-loader.mjs` redirects that one
 * specifier to a stub that throws a recognisable marker instead, so this
 * script can assert the real contract — `requireModule()` calls
 * `notFound()` exactly when the module is off — without reproducing Next's
 * whole module graph.
 *
 * `requireModule`/`requireModuleForAction` take an optional `site` override
 * precisely so this script (and any future test) can assert their behaviour
 * against a fixed `enabledModules` array with no reachable platform
 * database — every real caller omits it and gets the live `getSiteConfig()`.
 *
 * Run with:
 *   node --conditions react-server --experimental-strip-types scripts/verify-module-flags.mjs
 */
import { register } from 'node:module'

register('./lib/module-flags-loader.mjs', import.meta.url)

const { moduleEnabled, requireModule, requireModuleForAction } = await import('../src/lib/modules.ts')
const { modulesFrom } = await import('../src/lib/site.ts')
const { MODULE_LIST, MODULES } = await import('../src/lib/moduleNames.ts')
const { NOT_FOUND_MARKER } = await import('./lib/stub-next-navigation.mjs')

const failures = []
function check(ok, label, detail = '') {
  console.log(`[verify] ${ok ? 'PASS' : 'FAIL'} — ${label}${detail ? ` :: ${detail}` : ''}`)
  if (!ok) failures.push(label)
}
function eq(a, b, label) {
  check(JSON.stringify(a) === JSON.stringify(b), label, `got ${JSON.stringify(a)}`)
}
async function rejectsWithNotFound(promise, label) {
  try {
    await promise
    check(false, label, 'resolved instead of calling notFound()')
  } catch (err) {
    const ok = err?.message === NOT_FOUND_MARKER
    check(ok, label, ok ? '' : `threw, but not via notFound(): ${err}`)
  }
}
async function resolves(promise, label) {
  try {
    await promise
    check(true, label)
  } catch (err) {
    check(false, label, String(err))
  }
}

/* ------------------------------------------------------------ moduleEnabled */

eq(moduleEnabled({ enabledModules: [MODULES.print] }, MODULES.print), true, 'moduleEnabled: on when listed')
eq(moduleEnabled({ enabledModules: [MODULES.print] }, MODULES.reading), false, 'moduleEnabled: off when not listed')
eq(moduleEnabled({ enabledModules: [] }, MODULES.print), false, 'moduleEnabled: off on an empty array')
for (const module of MODULE_LIST) {
  eq(moduleEnabled({ enabledModules: [] }, module), false, `moduleEnabled: ${module} is off when enabledModules is []`)
}

/* ------------------------------------------------------------- modulesFrom */

eq(modulesFrom(['print', 'offers']), ['print', 'offers'], 'modulesFrom: keeps recognised module names')
eq(modulesFrom(['print', 'not-a-module']), ['print'], 'modulesFrom: silently drops an unrecognised entry')
eq(modulesFrom(null), [], 'modulesFrom: null (a row before this migration touched it) reads as nothing enabled')
eq(modulesFrom({}), [], 'modulesFrom: the jsonb-style ungoverned default {} also reads as nothing enabled')
eq(modulesFrom('print'), [], 'modulesFrom: a bare string (wrong shape) reads as nothing enabled')

/* -------------------------------------------------------------- requireModule */

await resolves(
  requireModule(MODULES.itineraries, { enabledModules: [MODULES.itineraries] }),
  'requireModule: resolves without throwing when the module is on',
)
await rejectsWithNotFound(
  requireModule(MODULES.itineraries, { enabledModules: [] }),
  'requireModule: calls notFound() when the module is off',
)
await rejectsWithNotFound(
  requireModule(MODULES.partnerPortal, { enabledModules: [MODULES.print, MODULES.newsletter] }),
  'requireModule: calls notFound() when off among other enabled modules',
)

/* ------------------------------------------------------- requireModuleForAction */

const onGate = await requireModuleForAction(MODULES.offers, { enabledModules: [MODULES.offers] })
check(onGate === null, 'requireModuleForAction: returns null (proceed) when the module is on')

const offGate = await requireModuleForAction(MODULES.offers, { enabledModules: [] })
check(
  offGate !== null && offGate.ok === false && /not available/.test(offGate.message),
  'requireModuleForAction: returns { ok: false, message } instead of throwing when off',
  JSON.stringify(offGate),
)

if (failures.length > 0) {
  console.error(`\n[verify] FAILED — ${failures.length} check(s): ${failures.join('; ')}`)
  process.exit(1)
}
console.log('\n[verify] OK — moduleEnabled/requireModule/requireModuleForAction agree with modulesFrom.')
process.exit(0)
