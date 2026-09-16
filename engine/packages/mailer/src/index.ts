/**
 * Transactional email (E8.0 — docs/READER-IDENTITY.md).
 *
 * Built because nothing in the stack could send mail, which blocked email
 * verification, password reset, and — already live and silently broken — the
 * newsletter's double opt-in (F135).
 *
 * Three ideas hold it together:
 *
 *   - **SMTP, not a vendor SDK.** Every provider speaks it, so switching is a
 *     config change; Mailpit speaks it, so local development is the same code.
 *   - **The transport is an interface.** `MemoryTransport` lets the policy
 *     above it — expiry wording, link construction, failure handling — be
 *     tested without a network, the same seam `@now/auth` puts at
 *     `IdentityStore`.
 *   - **Links come from configuration, never from a request header.** See
 *     `links.ts`; this is the one genuinely security-critical file here.
 */

export { Mailer, createTransportFromEnv } from './mailer.ts'
export type {
  MailerOptions,
  TransportEnv,
  TransportFailure,
  TransportResult,
} from './mailer.ts'

export { buildLink } from './links.ts'
export type { LinkFailure, LinkOptions, LinkResult } from './links.ts'

export { formatAddress, looksLikeAddress, normaliseEmail, validate } from './message.ts'
export type {
  Address,
  MessageProblem,
  OutboundMessage,
  ValidationResult,
} from './message.ts'

export { newsletterConfirm, resetPassword, verifyEmail } from './templates.ts'
export type { Branding, Rendered } from './templates.ts'

export { ConsoleTransport, MemoryTransport } from './transport.ts'
export type { Envelope, SendFailure, SendResult, Transport } from './transport.ts'

export { SmtpTransport } from './smtp.ts'
export type { SmtpConfig } from './smtp.ts'
