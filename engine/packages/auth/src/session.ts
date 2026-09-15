/**
 * The signed session token a city app issues after a platform sign-in.
 *
 * **Why a token at all.** The city app's Payload is bound to the city
 * database and has `disableLocalStrategy: true` — it cannot check a password,
 * because the credential lives in the platform database. So the login route
 * verifies against the platform (`authenticate()`), then issues this token,
 * and Payload's custom strategy trades it back for the shadow user on every
 * request. The token is the only thing carrying identity between those two
 * halves.
 *
 * **Why HMAC rather than a JWT library.** The payload is four fields we
 * control, the algorithm is fixed, and there is no negotiation — which
 * removes the entire class of JWT bugs that come from honouring an
 * attacker-supplied `alg` header (`none`, or HS256-signed-with-the-RSA-public
 * key). `verifySessionToken` below never reads an algorithm from the token;
 * it only ever computes HMAC-SHA256 and compares in constant time.
 *
 * **What the token is not.** It is not encrypted. Anyone holding it can read
 * the email and roles inside. That is fine — they are not secrets, and the
 * signature is what makes them trustworthy — but it means the token itself is
 * a bearer credential and must be carried in an httpOnly, secure, SameSite
 * cookie, never in a URL or localStorage.
 */

import crypto from 'node:crypto'

import type { CommerceRole, EditorialRole } from './identity.ts'

/** Eight hours, matching the console's existing `tokenExpiration`. */
export const DEFAULT_SESSION_TTL_SECONDS = 60 * 60 * 8

export type SessionClaims = {
  /** `public.users.id` in the CITY database — what Payload's session is for. */
  shadowId: number
  email: string
  editorialRole: EditorialRole
  commerceRole: CommerceRole
  /** Unix seconds. */
  exp: number
}

export type VerifyFailure = 'malformed' | 'bad_signature' | 'expired'

export type VerifyResult =
  | { ok: true; claims: SessionClaims }
  | { ok: false; reason: VerifyFailure }

function base64url(input: Buffer | string): string {
  return Buffer.from(input).toString('base64url')
}

function sign(body: string, secret: string): Buffer {
  return crypto.createHmac('sha256', secret).update(body).digest()
}

/**
 * Issues a token for a user who has just authenticated against the platform.
 *
 * `ttlSeconds` is deliberately short. The whole point of a central identity
 * store is that a revoked role stops working — but this token carries a copy
 * of the roles, so revocation only takes effect when it expires and the user
 * signs in again. Every second of TTL is a second a revoked editor keeps
 * their access.
 */
export function issueSessionToken(
  claims: Omit<SessionClaims, 'exp'>,
  secret: string,
  options: { ttlSeconds?: number; now?: () => Date } = {},
): string {
  if (!secret) throw new Error('refusing to sign a session token with an empty secret')

  const now = options.now ?? (() => new Date())
  const ttl = options.ttlSeconds ?? DEFAULT_SESSION_TTL_SECONDS
  const full: SessionClaims = {
    ...claims,
    exp: Math.floor(now().getTime() / 1000) + ttl,
  }

  const body = base64url(JSON.stringify(full))
  return `${body}.${base64url(sign(body, secret))}`
}

/**
 * Verifies and decodes a token.
 *
 * Order matters: the signature is checked **before** the payload is trusted
 * for anything, including expiry. Reading `exp` from an unverified token and
 * acting on it would let an attacker mint whatever expiry they liked.
 */
export function verifySessionToken(
  token: string,
  secret: string,
  options: { now?: () => Date } = {},
): VerifyResult {
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

  let claims: SessionClaims
  try {
    claims = JSON.parse(Buffer.from(body, 'base64url').toString('utf8'))
  } catch {
    return { ok: false, reason: 'malformed' }
  }

  if (
    typeof claims !== 'object' ||
    claims === null ||
    typeof claims.shadowId !== 'number' ||
    typeof claims.email !== 'string' ||
    typeof claims.exp !== 'number'
  ) {
    return { ok: false, reason: 'malformed' }
  }

  const now = options.now ?? (() => new Date())
  if (claims.exp * 1000 <= now().getTime()) {
    return { ok: false, reason: 'expired' }
  }

  return { ok: true, claims }
}

/**
 * The cookie the token travels in.
 *
 * `__Host-` is not decoration: the prefix is enforced by the browser, which
 * refuses the cookie unless it is Secure, path `/`, and has no Domain — so a
 * subdomain cannot set or overwrite it. That closes session fixation from a
 * neighbouring host on the same registrable domain, which matters here
 * because the admin now shares a hostname with the public reader site.
 */
export const SESSION_COOKIE = '__Host-now-staff'

export function sessionCookieOptions(ttlSeconds = DEFAULT_SESSION_TTL_SECONDS) {
  return {
    httpOnly: true,
    secure: true,
    sameSite: 'lax' as const,
    path: '/',
    maxAge: ttlSeconds,
  }
}
