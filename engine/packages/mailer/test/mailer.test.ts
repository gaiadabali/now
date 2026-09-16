import assert from 'node:assert/strict'
import { test } from 'node:test'

import { Mailer, createTransportFromEnv } from '../src/mailer.ts'
import { SmtpTransport } from '../src/smtp.ts'
import { MemoryTransport } from '../src/transport.ts'

const FROM = { email: 'hello@gaiada.com', name: 'NOW! Jakarta' }

function mailer() {
  const transport = new MemoryTransport()
  return { transport, mailer: new Mailer({ transport, from: FROM }) }
}

test('a valid message reaches the transport with the envelope sender attached', async () => {
  const { transport, mailer: m } = mailer()
  const result = await m.send({ to: { email: 'reader@example.com' }, subject: 'Hi', text: 'Body' })

  assert.equal(result.ok, true)
  assert.equal(transport.sent.length, 1)
  assert.deepEqual(transport.last()?.from, FROM)
})

test('invalid messages never reach the transport', async () => {
  const { transport, mailer: m } = mailer()
  const cases: [string, Parameters<Mailer['send']>[0]][] = [
    ['no recipient', { to: { email: '' }, subject: 's', text: 't' }],
    ['bad recipient', { to: { email: 'not-an-address' }, subject: 's', text: 't' }],
    ['no subject', { to: { email: 'a@b.com' }, subject: '  ', text: 't' }],
    ['no text part', { to: { email: 'a@b.com' }, subject: 's', text: '' }],
  ]
  for (const [label, message] of cases) {
    const result = await m.send(message)
    assert.equal(result.ok, false, label)
    assert.equal(!result.ok && result.reason, 'invalid_message', label)
  }
  assert.equal(transport.sent.length, 0)
})

test('header injection is refused, not stripped', async () => {
  const { transport, mailer: m } = mailer()
  const result = await m.send({
    to: { email: 'a@b.com', name: 'Real\r\nBcc: attacker@example.com' },
    subject: 'Hi',
    text: 'Body',
  })
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.detail, 'header_injection')
  assert.equal(transport.sent.length, 0)
})

test('a newline in the subject is refused', async () => {
  const { mailer: m } = mailer()
  const result = await m.send({
    to: { email: 'a@b.com' },
    subject: 'Hi\nBcc: attacker@example.com',
    text: 'Body',
  })
  assert.equal(result.ok, false)
})

test('a transport failure is returned, not thrown', async () => {
  const { transport, mailer: m } = mailer()
  transport.failNext = 1
  const result = await m.send({ to: { email: 'a@b.com' }, subject: 's', text: 't' })
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'transport_unavailable')
})

// --- transport selection ---------------------------------------------------

test('console transport is refused in production', () => {
  const result = createTransportFromEnv({ NODE_ENV: 'production', MAIL_TRANSPORT: 'console' })
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'console_in_production')
})

test('production with no SMTP_HOST fails rather than silently using the console', () => {
  // The dangerous default: no configuration at all, in production.
  const result = createTransportFromEnv({ NODE_ENV: 'production' })
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'console_in_production')
})

test('console is the default in development', () => {
  const result = createTransportFromEnv({})
  assert.equal(result.ok, true)
  assert.equal(result.ok && result.transport.name, 'console')
})

test('SMTP_HOST alone selects smtp', () => {
  const result = createTransportFromEnv({ SMTP_HOST: 'smtp.example.com' })
  assert.equal(result.ok, true)
  assert.equal(result.ok && result.transport.name, 'smtp://smtp.example.com:587')
})

test('smtp without a host is refused', () => {
  const result = createTransportFromEnv({ MAIL_TRANSPORT: 'smtp' })
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'missing_host')
})

test('an unrecognised transport name is refused', () => {
  const result = createTransportFromEnv({ MAIL_TRANSPORT: 'sendgrid' })
  assert.equal(result.ok, false)
  assert.equal(!result.ok && result.reason, 'unknown_transport')
})

test('port 465 implies implicit TLS without setting SMTP_SECURE', () => {
  // The documented production config (Hostinger). Getting this wrong means
  // speaking plaintext at a port expecting TLS, which fails as a timeout
  // rather than as anything that names the cause.
  const result = createTransportFromEnv({ SMTP_HOST: 'smtp.hostinger.com', SMTP_PORT: '465' })
  assert.equal(result.ok, true)
  assert.equal(result.ok && result.transport.name, 'smtp://smtp.hostinger.com:465')
  assert.equal(result.ok && (result.transport as SmtpTransport).settings.secure, true)
})

test('port 587 stays STARTTLS, not implicit TLS', () => {
  const result = createTransportFromEnv({ SMTP_HOST: 'smtp.hostinger.com', SMTP_PORT: '587' })
  assert.equal(result.ok && (result.transport as SmtpTransport).settings.secure, false)
})

test('SMTP_SECURE still overrides the port-derived default', () => {
  const result = createTransportFromEnv({
    SMTP_HOST: 'relay.internal',
    SMTP_PORT: '465',
    SMTP_SECURE: 'false',
  })
  assert.equal(result.ok && (result.transport as SmtpTransport).settings.secure, false)
})

test('self-signed certs are never allowed in production, whatever the env says', () => {
  const result = createTransportFromEnv({
    NODE_ENV: 'production',
    SMTP_HOST: 'smtp.hostinger.com',
    SMTP_PORT: '465',
    SMTP_ALLOW_SELF_SIGNED: 'true',
  })
  assert.equal(result.ok && (result.transport as SmtpTransport).settings.allowSelfSigned, false)
})

test('self-signed IS allowed outside production, for mailpit', () => {
  const result = createTransportFromEnv({
    SMTP_HOST: '127.0.0.1',
    SMTP_PORT: '1025',
    SMTP_ALLOW_SELF_SIGNED: 'true',
  })
  assert.equal(result.ok && (result.transport as SmtpTransport).settings.allowSelfSigned, true)
})

test('the transport name never carries a credential', () => {
  const result = createTransportFromEnv({
    SMTP_HOST: 'smtp.example.com',
    SMTP_USER: 'apikey',
    SMTP_PASSWORD: 'super-secret',
  })
  assert.equal(result.ok, true)
  assert.ok(result.ok && !result.transport.name.includes('super-secret'))
  assert.ok(result.ok && !result.transport.name.includes('apikey'))
})
