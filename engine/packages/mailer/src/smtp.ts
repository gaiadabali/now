/**
 * SMTP, via nodemailer.
 *
 * ## Why SMTP and not a provider SDK
 *
 * Every transactional provider worth using — SES, Postmark, Resend, SendGrid,
 * Mailgun — speaks SMTP, and so does a self-hosted relay. One transport
 * therefore covers all of them, changing provider is a change of environment
 * variables rather than a change of code, and local development points at
 * Mailpit with the same object. A vendor SDK buys webhooks and analytics this
 * package does not use, in exchange for a lock-in it does not need.
 *
 * ## Why nodemailer and not hand-rolled SMTP
 *
 * The same reasoning `@now/auth`'s `password.ts` applies to PBKDF2, in the
 * other direction: that file reimplements one well-specified function because
 * it *must* match Payload byte-for-byte. SMTP is not one function. It is
 * connection management, STARTTLS negotiation, AUTH mechanisms, MIME
 * assembly, encoding and dot-stuffing — and getting MIME subtly wrong produces
 * mail that renders as raw source in one client and fine in another.
 */

import nodemailer from 'nodemailer'
import type { Transporter } from 'nodemailer'

import { formatAddress } from './message.ts'
import type { Envelope, SendResult, Transport } from './transport.ts'

export type SmtpConfig = {
  host: string
  port: number
  /** Implicit TLS (port 465). Port 587 upgrades with STARTTLS instead. */
  secure: boolean
  user?: string
  password?: string
  /**
   * Local relays (Mailpit, MailHog) present a self-signed certificate. Only
   * ever set from an explicit dev environment variable — see
   * `createTransportFromEnv`, which refuses it under NODE_ENV=production.
   */
  allowSelfSigned?: boolean
}

export class SmtpTransport implements Transport {
  readonly name: string
  /**
   * The resolved settings, **without the password**.
   *
   * Exposed because `secure` and `allowSelfSigned` are decisions made from
   * other inputs (the port, NODE_ENV) rather than passed straight through,
   * and a decision nothing can observe is a decision nothing can test. A
   * wrong `secure` fails as a connection timeout, which names nothing.
   */
  readonly settings: Omit<SmtpConfig, 'password'>
  private transporter: Transporter

  constructor(config: SmtpConfig) {
    const { password: _password, ...rest } = config
    void _password
    this.settings = rest
    // The name is logged at startup, so it carries host and port and
    // deliberately not the user or password.
    this.name = `smtp://${config.host}:${config.port}`
    this.transporter = nodemailer.createTransport({
      host: config.host,
      port: config.port,
      secure: config.secure,
      auth: config.user ? { user: config.user, pass: config.password } : undefined,
      tls: config.allowSelfSigned ? { rejectUnauthorized: false } : undefined,
      // A request thread waiting on a wedged SMTP connection is a request
      // thread not serving anyone. Fail and let the caller decide.
      connectionTimeout: 10_000,
      greetingTimeout: 10_000,
      socketTimeout: 20_000,
    })
  }

  async send(envelope: Envelope): Promise<SendResult> {
    try {
      const info = await this.transporter.sendMail({
        from: formatAddress(envelope.from),
        to: formatAddress(envelope.to),
        replyTo: envelope.replyTo ? formatAddress(envelope.replyTo) : undefined,
        subject: envelope.subject,
        text: envelope.text,
        html: envelope.html,
      })
      return { ok: true, id: info.messageId }
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error)
      // A 5xx from the server is the server refusing this message; anything
      // else is the connection. The distinction matters to the caller: a
      // rejection will happen again on retry, an outage will not.
      const rejected = /\b5\d\d\b/.test(detail)
      return {
        ok: false,
        reason: rejected ? 'rejected' : 'transport_unavailable',
        detail,
      }
    }
  }

  /** Proves host, port and credentials before the first real send. */
  async verify(): Promise<SendResult> {
    try {
      await this.transporter.verify()
      return { ok: true, id: 'verified' }
    } catch (error) {
      return {
        ok: false,
        reason: 'transport_unavailable',
        detail: error instanceof Error ? error.message : String(error),
      }
    }
  }
}
