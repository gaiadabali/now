/**
 * `buildLink` is the security-critical file in this package, so these are
 * mostly attack tests rather than formatting ones.
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { buildLink } from '../src/links.ts'

const BASE = 'https://now-jakarta.gaiada.com'

test('builds a link with encoded params', () => {
  const result = buildLink(BASE, '/verify', { token: 'a b&c=d' })
  assert.equal(result.ok, true)
  assert.equal(result.ok && result.url, 'https://now-jakarta.gaiada.com/verify?token=a+b%26c%3Dd')
})

test('an unconfigured base cannot produce a link', () => {
  for (const base of [undefined, '', '   ']) {
    const result = buildLink(base, '/verify', { token: 't' })
    assert.equal(result.ok, false)
    assert.equal(!result.ok && result.reason, 'unconfigured_base')
  }
})

test('http is refused unless explicitly allowed', () => {
  const refused = buildLink('http://localhost:3000', '/verify', { token: 't' })
  assert.equal(refused.ok, false)
  assert.equal(!refused.ok && refused.reason, 'insecure_base')

  const allowed = buildLink('http://localhost:3000', '/verify', { token: 't' }, { allowInsecure: true })
  assert.equal(allowed.ok, true)
})

test('a non-http scheme is refused', () => {
  for (const base of ['javascript:alert(1)', 'file:///etc/passwd', 'ftp://example.com']) {
    const result = buildLink(base, '/verify', { token: 't' })
    assert.equal(result.ok, false, `${base} should not build`)
  }
})

test('an absolute path cannot replace the configured origin', () => {
  // The whole point: even if a caller passes something absolute, the host
  // stays the configured one. The attacker's string survives as an inert path
  // segment, which is harmless — what matters is that nothing resolves to it.
  const result = buildLink(BASE, 'https://attacker.example/steal', { token: 't' })
  assert.equal(result.ok, true)
  assert.equal(result.ok && new URL(result.url).origin, 'https://now-jakarta.gaiada.com')
  assert.equal(result.ok && new URL(result.url).host, 'now-jakarta.gaiada.com')
})

test('a protocol-relative path cannot redirect the host', () => {
  // `//attacker.example/x` is the form that slips past a naive check: it has
  // no scheme, so a string test for "https://" misses it, and a browser reads
  // it as an absolute URL on the current protocol.
  const result = buildLink(BASE, '//attacker.example/steal', { token: 't' })
  assert.equal(result.ok, true)
  assert.equal(result.ok && new URL(result.url).host, 'now-jakarta.gaiada.com')
})

test('a query string on the configured base cannot smuggle a parameter', () => {
  const result = buildLink(`${BASE}/?token=attacker`, '/verify', { token: 'real' })
  assert.equal(result.ok, true)
  assert.equal(result.ok && new URL(result.url).searchParams.get('token'), 'real')
  assert.equal(result.ok && new URL(result.url).searchParams.getAll('token').length, 1)
})

test('a base with a path prefix keeps it', () => {
  const result = buildLink('https://example.com/city', '/verify', { token: 't' })
  assert.equal(result.ok, true)
  assert.equal(result.ok && new URL(result.url).pathname, '/city/verify')
})

test('slashes do not double up', () => {
  for (const [base, path] of [
    ['https://example.com', '/verify'],
    ['https://example.com/', '/verify'],
    ['https://example.com/', 'verify'],
    ['https://example.com', 'verify'],
  ] as const) {
    const result = buildLink(base, path, {})
    assert.equal(result.ok, true)
    assert.equal(result.ok && new URL(result.url).pathname, '/verify', `${base} + ${path}`)
  }
})

test('a fragment on the base is dropped', () => {
  const result = buildLink(`${BASE}/#/spa`, '/verify', { token: 't' })
  assert.equal(result.ok, true)
  assert.equal(result.ok && new URL(result.url).hash, '')
})
