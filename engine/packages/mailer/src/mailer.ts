/**
 * The object the application holds: a transport, a sender identity, and the
 * validation every message passes through on the way out.
 *
 * `send` returns a result rather than throwing. A failed verification mail is
 * a thing the caller has to make a decision about — the account was still
 * created, and the right response is "we could not email you, here is how to
 * retry", not a 500 that loses the registration.
 */

import { validate } from './message.ts'
import type { Address, OutboundMessage } from './message.ts'
import { SmtpTransport } from './smtp.ts'
import { ConsoleTransport } from './transport.ts'
import type { Envelope, SendResult, Transport } from './transport.ts'

export type MailerOptions = {
  transport: Transport
  /** Envelope sender. Must be on a domain whose SPF/DKIM you control. */
  from: Address
  replyTo?: Address
}

export class Mailer {
  // Declared explicitly rather than as a constructor parameter property:
  // `node --experimental-strip-types` runs this package's tests with no build
  // step, and strip-only mode cannot desugar `constructor(private x)`.
  private readonly options: MailerOptions

  constructor(options: MailerOptions) {
    this.options = options
  }

  get transportName(): string {
    return this.options.transport.name
  }

  async send(message: OutboundMessage): Promise<SendResult> {
    const check = validate(message)
    if (!check.ok) {
      // The reason is returned, not logged with the address attached. A
      // rejected recipient is still a recipient someone typed.
      return { ok: false, reason: 'invalid_message', detail: check.reason }
    }
    const envelope: Envelope = {
      ...message,
      from: this.options.from,
      replyTo: message.replyTo ?? this.options.replyTo,
    }
    return this.options.transport.send(envelope)
  }
}

export type TransportEnv = {
  SMTP_HOST?: string
  SMTP_PORT?: string
  SMTP_USER?: string
  SMTP_PASSWORD?: string
  SMTP_SECURE?: string
  SMTP_ALLOW_SELF_SIGNED?: string
  MAIL_TRANSPORT?: string
  NODE_ENV?: string
}

export type TransportFailure = 'console_in_production' | 'missing_host' | 'unknown_transport'

export type TransportResult =
  | { ok: true; transport: Transport }
  | { ok: false; reason: TransportFailure; detail: string }

/**
 * Chooses a transport from the environment, and **refuses the dangerous
 * combination** rather than warning about it.
 *
 * `MAIL_TRANSPORT=console` prints verification links to stdout. In development
 * that is the feature. In production it is an outage that looks like success:
 * every registration appears to work, no mail is ever sent, and the logs fill
 * with live single-use credentials. So it is refused outright under
 * `NODE_ENV=production` — a deployment that gets this wrong fails at startup,
 * which is the cheapest place to find out.
 */
export function createTransportFromEnv(
  // `process.env` is `ProcessEnv`, whose index signature shares no *declared*
  // property with `TransportEnv`, so TypeScript's weak-type check rejects it.
  // The cast narrows to the handful of keys actually read below; tests pass a
  // literal and get the real checking.
  env: TransportEnv = process.env as TransportEnv,
): TransportResult {
  const production = env.NODE_ENV === 'production'
  const choice = env.MAIL_TRANSPORT ?? (env.SMTP_HOST ? 'smtp' : 'console')

  if (choice === 'console') {
    if (production) {
      return {
        ok: false,
        reason: 'console_in_production',
        detail:
          'MAIL_TRANSPORT=console prints verification links to stdout and sends nothing. Set SMTP_HOST, or set MAIL_TRANSPORT=smtp explicitly.',
      }
    }
    return { ok: true, transport: new ConsoleTransport() }
  }

  if (choice === 'smtp') {
    if (!env.SMTP_HOST) {
      return { ok: false, reason: 'missing_host', detail: 'MAIL_TRANSPORT=smtp requires SMTP_HOST.' }
    }
    const port = Number(env.SMTP_PORT ?? 587)
    return {
      ok: true,
      transport: new SmtpTransport({
        host: env.SMTP_HOST,
        port,
        // 465 is implicit TLS; 587 negotiates STARTTLS. Defaulting off the
        // port number is right far more often than defaulting to false.
        secure: env.SMTP_SECURE ? env.SMTP_SECURE === 'true' : port === 465,
        user: env.SMTP_USER,
        password: env.SMTP_PASSWORD,
        // Never in production, whatever the variable says.
        allowSelfSigned: !production && env.SMTP_ALLOW_SELF_SIGNED === 'true',
      }),
    }
  }

  return {
    ok: false,
    reason: 'unknown_transport',
    detail: `MAIL_TRANSPORT must be 'smtp' or 'console', got '${choice}'.`,
  }
}
