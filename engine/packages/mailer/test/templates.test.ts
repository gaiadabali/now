import assert from 'node:assert/strict'
import { test } from 'node:test'

import { newsletterConfirm, resetPassword, verifyEmail } from '../src/templates.ts'

const BRANDING = { siteName: 'NOW! Jakarta', supportEmail: 'hello@gaiada.com' }
const URL_ = 'https://now-jakarta.gaiada.com/verify?token=abc123'

const ALL = [
  ['verifyEmail', verifyEmail(BRANDING, URL_, 24)],
  ['resetPassword', resetPassword(BRANDING, URL_, 1)],
  ['newsletterConfirm', newsletterConfirm(BRANDING, URL_)],
] as const

test('every template renders a subject, a text part and an html part', () => {
  for (const [name, rendered] of ALL) {
    assert.ok(rendered.subject.trim().length > 0, `${name} subject`)
    assert.ok(rendered.text.trim().length > 0, `${name} text`)
    assert.ok(rendered.html.trim().length > 0, `${name} html`)
  }
})

test('the link appears in BOTH parts — a text part without it is a dead end', () => {
  for (const [name, rendered] of ALL) {
    assert.ok(rendered.text.includes(URL_), `${name} text is missing the link`)
    assert.ok(rendered.html.includes('token=abc123'), `${name} html is missing the link`)
  }
})

test('no subject carries a newline', () => {
  for (const [name, rendered] of ALL) {
    assert.ok(!/[\r\n]/.test(rendered.subject), `${name} subject`)
  }
})

test('every template names the site and the support address', () => {
  for (const [name, rendered] of ALL) {
    assert.ok(rendered.subject.includes('NOW! Jakarta'), `${name} subject`)
    assert.ok(rendered.html.includes('hello@gaiada.com'), `${name} support address`)
  }
})

test('branding is escaped into the html', () => {
  const rendered = verifyEmail(
    { siteName: '<script>alert(1)</script>', supportEmail: 'a@b.com' },
    URL_,
    24,
  )
  assert.ok(!rendered.html.includes('<script>'))
  assert.ok(rendered.html.includes('&lt;script&gt;'))
})

test('a link with html-significant characters is escaped in the href', () => {
  const nasty = 'https://example.com/verify?token=a"onmouseover="alert(1)'
  const rendered = verifyEmail(BRANDING, nasty, 24)
  assert.ok(!rendered.html.includes('onmouseover="alert(1)"'))
  assert.ok(rendered.html.includes('&quot;'))
})

test('the reset mail does not assert that the recipient asked for it', () => {
  // Someone receiving an unrequested reset did not ask. Telling them they did
  // is how a phishing mail reads, and it trains readers to distrust the real
  // one.
  const rendered = resetPassword(BRANDING, URL_, 1)
  assert.ok(rendered.text.startsWith('Someone asked'))
  assert.ok(/not you/i.test(rendered.text))
})

test('both account mails state a single-use expiry', () => {
  assert.ok(/expires in 24 hours/.test(verifyEmail(BRANDING, URL_, 24).text))
  assert.ok(/expires in 1 hour\b/.test(resetPassword(BRANDING, URL_, 1).text))
  for (const [, rendered] of ALL.slice(0, 2)) {
    assert.ok(/used once/.test(rendered.text))
  }
})

test('every template tells an unintended recipient that ignoring it is safe', () => {
  for (const [name, rendered] of ALL) {
    assert.ok(/ignore this email/i.test(rendered.text), `${name}`)
  }
})
