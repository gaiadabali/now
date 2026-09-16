/**
 * The signing and verification underneath every session token in this package.
 *
 * Extracted when readers got sessions of their own (E8.2). Staff and readers
 * are deliberately separate populations with separate stores, separate cookies
 * and separate secrets — but they must not have separate *crypto*. Two
 * implementations of the same HMAC is how you end up with two security levels
 * and only one of them reviewed, which is the argument `password.ts` already
 * makes about hashing.
 *
 * What lives here: encode, sign, verify, constant-time compare. What does not:
 * any notion of what a claim means. Shape validation, expiry and audience are
 * the caller's, because those are the parts that differ between a staff token
 * carrying roles and a reader token carrying none.
 *
 * **Why HMAC rather than a JWT library** (unchanged from the original
 * `session.ts`): the payload is a few fields we control, the algorithm is
 * fixed, and there is no negotiation — which removes the entire class of JWT
 * bugs that come from honouring an attacker-supplied `alg` header (`none`, or
 * HS256-signed-with-the-RSA-public-key). Nothing here ever reads an algorithm
 * from a token; it only ever computes HMAC-SHA256 and compares in constant
 * time.
 *
 * **These tokens are signed, not encrypted.** Anyone holding one can read the
 * claims inside. That is fine — they are not secrets, and the signature is
 * what makes them trustworthy — but it means the token is a bearer credential
 * and must travel in an httpOnly, secure cookie, never a URL or localStorage.
 */

import crypto from 'node:crypto'

export type DecodeFailure = 'malformed' | 'bad_signature'

export type DecodeResult =
  | { ok: true; claims: Record<string, unknown> }
  | { ok: false; reason: DecodeFailure }

function base64url(input: Buffer | string): string {
  return Buffer.from(input).toString('base64url')
}

function sign(body: string, secret: string): Buffer {
  return crypto.createHmac('sha256', secret).update(body).digest()
}

/** Signs an already-complete claims object. Expiry is the caller's to set. */
export function encodeToken(claims: object, secret: string): string {
  if (!secret) throw new Error('refusing to sign a session token with an empty secret')
  const body = base64url(JSON.stringify(claims))
  return `${body}.${base64url(sign(body, secret))}`
}

/**
 * Verifies the signature and returns the raw claims.
 *
 * Order matters: the signature is checked **before** the payload is parsed for
 * anything. Reading a claim from an unverified token and acting on it — an
 * expiry, an id, an audience — is trusting input an attacker wrote.
 */
export function decodeToken(token: string, secret: string): DecodeResult {
  if (!secret) throw new Error('refusing to verify a session token with an empty secret')
  if (typeof token !== 'string' || token.length === 0) {
    return { ok: false, reason: 'malformed' }
  }

  const parts = token.split('.')
  if (parts.length !== 2) return { ok: false, reason: 'malformed' }
  const [body, providedSignature] = parts as [string, string]

  const expected = sign(body, secret)
  let provided: Buffer
  try {
    provided = Buffer.from(providedSignature, 'base64url')
  } catch {
    return { ok: false, reason: 'malformed' }
  }
  // Length must match before timingSafeEqual, which throws on a mismatch.
  if (provided.length !== expected.length) return { ok: false, reason: 'bad_signature' }
  if (!crypto.timingSafeEqual(provided, expected)) return { ok: false, reason: 'bad_signature' }

  let claims: unknown
  try {
    claims = JSON.parse(Buffer.from(body, 'base64url').toString('utf8'))
  } catch {
    return { ok: false, reason: 'malformed' }
  }

  if (typeof claims !== 'object' || claims === null || Array.isArray(claims)) {
    return { ok: false, reason: 'malformed' }
  }

  return { ok: true, claims: claims as Record<string, unknown> }
}

/**
 * Who a token is for.
 *
 * Third line of defence, behind separate cookie names and separate signing
 * secrets. Those two should already make a reader token unusable on a staff
 * route — it is never presented, and would not verify if it were. `aud` is
 * what still holds the day someone reuses a secret by accident, which is the
 * kind of mistake that is invisible until it is exploited.
 */
export type Audience = 'staff' | 'reader'

/**
 * Staff tokens issued before E8.2 carry no `aud`, and rejecting those would
 * sign out every editor mid-session for no security gain — the cookie name
 * already separates them. So a *missing* audience is accepted by whichever
 * caller expects it, and a *present, wrong* one never is. Reader tokens have
 * always carried `aud`, so there is no equivalent gap on that side.
 */
export function audienceMatches(claims: Record<string, unknown>, expected: Audience): boolean {
  const aud = claims.aud
  if (aud === undefined) return expected === 'staff'
  return aud === expected
}
