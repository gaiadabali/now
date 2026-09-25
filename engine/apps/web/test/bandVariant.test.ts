import assert from 'node:assert/strict'
import { test } from 'node:test'

import { departmentVariant } from '../src/lib/bandVariant.ts'

test('the first department band on the page is always ivory', () => {
  assert.equal(departmentVariant(0), 'ivory')
})

test('ivory is never revisited past the first department band', () => {
  // 0..9: only index 0 may ever be 'ivory'.
  for (let i = 1; i < 10; i++) {
    assert.notEqual(departmentVariant(i), 'ivory', `index ${i} should not be ivory`)
  }
})

test('two adjacent department bands never share a treatment', () => {
  for (let i = 0; i < 9; i++) {
    assert.notEqual(departmentVariant(i), departmentVariant(i + 1), `index ${i} and ${i + 1} should differ`)
  }
})

test('cycles mirror/quad after the first', () => {
  assert.equal(departmentVariant(1), 'mirror')
  assert.equal(departmentVariant(2), 'quad')
  assert.equal(departmentVariant(3), 'mirror')
  assert.equal(departmentVariant(4), 'quad')
})
