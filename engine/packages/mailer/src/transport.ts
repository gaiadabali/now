/**
 * The seam between "what to send" and "how it leaves the building".
 *
 * Same shape as `@now/auth`'s `IdentityStore`, and for the same reason: the
 * policy above it — what a verification mail says, when a reset expires, what
 * a failure does to the request — is the part worth testing, and none of it
 * should need a network or a running SMTP server to exercise.
 */

import type { Address, OutboundMessage } from './message.ts'

export type SendFailure =
  | 'invalid_message'
  | 'rejected'
  | 'transport_unavailable'

export type SendResult =
  | { ok: true; id: string }
  | { ok: false; reason: SendFailure; detail?: string }

/** What a transport is handed: a validated message plus the envelope sender. */
export type Envelope = OutboundMessage & { from: Address }

export interface Transport {
  /** Human-readable, for startup logs. Never includes a credential. */
  readonly name: string
  send(envelope: Envelope): Promise<SendResult>
}

/**
 * Test double. Keeps every message so assertions can be made about content,
 * which is the whole point — a template that renders the wrong link is not
 * caught by asserting that `send` was called.
 */
export class MemoryTransport implements Transport {
  readonly name = 'memory'
  readonly sent: Envelope[] = []

  /** Set to fail the next N sends, for exercising the failure paths. */
  failNext = 0

  async send(envelope: Envelope): Promise<SendResult> {
    if (this.failNext > 0) {
      this.failNext -= 1
      return { ok: false, reason: 'transport_unavailable', detail: 'forced by test' }
    }
    this.sent.push(envelope)
    return { ok: true, id: `memory-${this.sent.length}` }
  }

  last(): Envelope | undefined {
    return this.sent.at(-1)
  }

  clear(): void {
    this.sent.length = 0
    this.failNext = 0
  }
}

/**
 * Local development without an SMTP server at all.
 *
 * Prints the message and — critically — the full body, because the body is
 * where the verification link is, and a developer who cannot read the link
 * cannot complete the flow they are building. This is exactly why it must
 * never be reachable in production: `createTransportFromEnv` refuses it when
 * `NODE_ENV=production`, rather than leaving that to a code review.
 */
export class ConsoleTransport implements Transport {
  readonly name = 'console'
  private n = 0
  // Explicit field, not a constructor parameter property — strip-only mode
  // cannot desugar those, and this package runs its tests unbuilt.
  private readonly write: (line: string) => void

  constructor(write: (line: string) => void = console.log) {
    this.write = write
  }

  async send(envelope: Envelope): Promise<SendResult> {
    this.n += 1
    this.write(
      [
        '',
        '─'.repeat(72),
        `  MAIL (not sent — console transport)`,
        `  to      ${envelope.to.email}`,
        `  subject ${envelope.subject}`,
        envelope.tag ? `  tag     ${envelope.tag}` : null,
        '─'.repeat(72),
        envelope.text,
        '─'.repeat(72),
        '',
      ]
        .filter((l) => l !== null)
        .join('\n'),
    )
    return { ok: true, id: `console-${this.n}` }
  }
}
