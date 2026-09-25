import assert from 'node:assert/strict'
import { test } from 'node:test'

import { safeInternalPath } from '../src/lib/internalPath.ts'

test('accepts a plain path', () => {
  assert.equal(safeInternalPath('/account'), '/account')
})

test('accepts a path with a query string and a fragment', () => {
  assert.equal(safeInternalPath('/some-article?ref=share#share'), '/some-article?ref=share#share')
})

test('rejects null and undefined', () => {
  assert.equal(safeInternalPath(null), null)
  assert.equal(safeInternalPath(undefined), null)
})

test('rejects the empty string', () => {
  assert.equal(safeInternalPath(''), null)
})

test('rejects a bare string with no leading slash', () => {
  assert.equal(safeInternalPath('account'), null)
})

test('rejects an absolute URL', () => {
  assert.equal(safeInternalPath('https://evil.example/'), null)
})

test('rejects a protocol-relative URL — a browser resolves it against its own scheme', () => {
  assert.equal(safeInternalPath('//evil.example'), null)
  assert.equal(safeInternalPath('//evil.example/path'), null)
})

test('rejects the backslash variant some browsers still fold into protocol-relative', () => {
  assert.equal(safeInternalPath('/\\evil.example'), null)
  assert.equal(safeInternalPath('/\\/evil.example'), null)
})

test('rejects a javascript: URL', () => {
  assert.equal(safeInternalPath('javascript:alert(1)'), null)
})

test('accepts a percent-encoded path that is not actually a redirect trick', () => {
  assert.equal(safeInternalPath('/%5C%5Cevil.example'), '/%5C%5Cevil.example')
})
