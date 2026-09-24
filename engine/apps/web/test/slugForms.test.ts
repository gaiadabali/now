import assert from 'node:assert/strict'
import { test } from 'node:test'

import { slugForms } from '../src/lib/format.ts'

test('a decoded non-ASCII address also tries the lower-case form WordPress stored', () => {
  assert.ok(slugForms('kita-喜多-restaurant').includes('kita-%e5%96%9c%e5%a4%9a-restaurant'))
})

test('the stored percent-encoded form, requested as-is, still resolves', () => {
  assert.ok(slugForms('kita-%e5%96%9c%e5%a4%9a-restaurant').includes('kita-%e5%96%9c%e5%a4%9a-restaurant'))
})

test('an ASCII address is tried exactly once', () => {
  assert.deepEqual(slugForms('ihg-hotels-resorts'), ['ihg-hotels-resorts'])
})

test('a stray percent sign does not throw', () => {
  assert.ok(slugForms('50%-off').includes('50%-off'))
})
