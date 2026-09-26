import assert from 'node:assert/strict'
import { test } from 'node:test'

import { isModuleName, mergeModuleSelection, MODULE_LABELS, MODULE_LIST, MODULES } from '../src/lib/moduleNames.ts'

/**
 * `lib/moduleNames.ts` is a deliberate leaf — no `@/*` alias, no `next/*`
 * import — so it is the one part of P0.3's module-flag machinery this suite
 * can exercise directly under plain `node --test`. `moduleEnabled()`,
 * `requireModule()` and `requireModuleForAction()` (`lib/modules.ts`) pull in
 * `lib/site.ts` → `lib/db.ts`, which needs the `@/*` alias resolved and the
 * `react-server` condition active for `server-only` — exactly the situation
 * `scripts/verify-site-config.mjs` already documents. Those three are
 * exercised instead by `scripts/verify-module-flags.mjs`, run with:
 *
 *   node --conditions react-server --experimental-strip-types scripts/verify-module-flags.mjs
 */

test('isModuleName accepts every known module and rejects everything else', () => {
  for (const module of MODULE_LIST) assert.equal(isModuleName(module), true)
  assert.equal(isModuleName('membership'), false)
  assert.equal(isModuleName(''), false)
  assert.equal(isModuleName(null), false)
  assert.equal(isModuleName(undefined), false)
  assert.equal(isModuleName(42), false)
})

test('the six P0.3 modules are exactly what the roadmap names', () => {
  assert.deepEqual(
    [...MODULE_LIST].sort(),
    ['itineraries', 'newsletter', 'offers', 'partner_portal', 'print', 'reading'].sort(),
  )
})

test('MODULES values match MODULE_LIST (no third spelling of a module name)', () => {
  assert.deepEqual(
    Object.values(MODULES).sort(),
    [...MODULE_LIST].sort(),
  )
})

test('every module has a human label, and no label is blank', () => {
  for (const module of MODULE_LIST) {
    assert.equal(typeof MODULE_LABELS[module], 'string')
    assert.notEqual(MODULE_LABELS[module].trim(), '')
  }
})

test('mergeModuleSelection keeps entries the toggle screen does not own', () => {
  assert.deepEqual(
    mergeModuleSelection(['feed', 'search', 'events'], ['print']),
    ['feed', 'search', 'events', 'print'],
  )
})

test('mergeModuleSelection replaces only the P0.3 part of the array', () => {
  assert.deepEqual(
    mergeModuleSelection(['feed', 'print', 'offers', 'events'], ['reading']),
    ['feed', 'events', 'reading'],
  )
  assert.deepEqual(mergeModuleSelection(['feed', 'print'], []), ['feed'])
})

test('mergeModuleSelection drops unknown selections, dedupes, and orders by MODULE_LIST', () => {
  assert.deepEqual(
    mergeModuleSelection(null, ['partner_portal', 'bogus', 'itineraries', 'itineraries', 42]),
    ['itineraries', 'partner_portal'],
  )
  assert.deepEqual(mergeModuleSelection(undefined, 'print'), [])
})
