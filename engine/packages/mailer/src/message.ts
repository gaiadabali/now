/**
 * What a message is, and what makes one invalid before it ever reaches a
 * transport.
 *
 * Validation lives here rather than in the transport because a malformed
 * message should fail the same way against SMTP, the console and the memory
 * double. A bug that only appears in production is one the test transport was
 * too permissive to catch.
 */

export type Address = {
  email: string
  /** Display name. Optional, and deliberately not defaulted to the address. */
  name?: string
}

export type OutboundMessage = {
  to: Address
  subject: string
  /**
   * Always required.
   *
   * A text/plain part is not a courtesy to people who turned images off — it
   * is a deliverability requirement. HTML-only mail scores as spam with every
   * major filter, and transactional mail that lands in spam is the same as
   * transactional mail that was never sent, except harder to diagnose.
   */
  text: string
  html?: string
  replyTo?: Address
  /**
   * Stable per logical send, used for `Message-ID` and for tracing a delivery
   * back to the thing that caused it. NOT an idempotency key — the transport
   * does not deduplicate, because a retried verification mail is a nuisance
   * and a swallowed one is a support ticket.
   */
  tag?: string
}

export type MessageProblem =
  | 'missing_recipient'
  | 'invalid_recipient'
  | 'missing_subject'
  | 'missing_text'
  | 'header_injection'

export type ValidationResult = { ok: true } | { ok: false; reason: MessageProblem }

/**
 * Deliberately permissive, matching `lib/newsletter.ts`'s reasoning: the only
 * thing worth rejecting is input that cannot be an address at all. A stricter
 * pattern rejects real addresses — plus-tags, new TLDs, unicode locals — and
 * the cost of a wrong rejection is a reader who cannot sign in and is told
 * nothing useful about why.
 */
export function looksLikeAddress(raw: string): boolean {
  const email = raw.trim()
  if (email.length < 5 || email.length > 254) return false
  const at = email.indexOf('@')
  if (at < 1 || at !== email.lastIndexOf('@')) return false
  const domain = email.slice(at + 1)
  if (!domain.includes('.') || domain.startsWith('.') || domain.endsWith('.')) return false
  if (/\s/.test(email)) return false
  return true
}

/** `lower(btrim(x))` — the same normalisation migration 0007 stores. */
export function normaliseEmail(raw: string): string {
  return raw.trim().toLowerCase()
}

/**
 * CR and LF in a header value let a caller append headers of their own —
 * a `Bcc:` to somewhere else, or a second body. Anything interpolated into
 * `Subject`, a display name or an address is attacker-influenced the moment a
 * reader controls their own name, so this is checked for every message rather
 * than at the one call site someone remembered.
 *
 * Checked, not stripped. Silently rewriting a subject hides the attempt;
 * refusing it leaves something to see in the logs.
 */
function hasHeaderInjection(...values: (string | undefined)[]): boolean {
  return values.some((v) => v !== undefined && /[\r\n]/.test(v))
}

export function validate(message: OutboundMessage): ValidationResult {
  if (!message.to?.email?.trim()) return { ok: false, reason: 'missing_recipient' }
  if (!looksLikeAddress(message.to.email)) return { ok: false, reason: 'invalid_recipient' }
  if (!message.subject?.trim()) return { ok: false, reason: 'missing_subject' }
  if (!message.text?.trim()) return { ok: false, reason: 'missing_text' }
  if (hasHeaderInjection(message.subject, message.to.name, message.to.email, message.replyTo?.email, message.replyTo?.name)) {
    return { ok: false, reason: 'header_injection' }
  }
  return { ok: true }
}

/** RFC 5322 display-name quoting, for transports that take a single string. */
export function formatAddress(address: Address): string {
  if (!address.name) return address.email
  const escaped = address.name.replace(/(["\\])/g, '\\$1')
  return `"${escaped}" <${address.email}>`
}
