/**
 * The reader's session token (E8.2 — docs/READER-IDENTITY.md).
 *
 * Shares `token.ts`'s crypto with the staff session and shares nothing else.
 * Three separations, because the thing that must never happen is a reader
 * session authenticating into `/team-editor`:
 *
 *   1. **A different cookie.** `__Host-now-reader`, not `__Host-now-staff`.
 *      Distinct names mean a reader's cookie is not even *presented* to the
 *      staff path, so the question never reaches a verifier.
 *   2. **A different secret.** `READER_SESSION_SECRET`, not `PAYLOAD_SECRET`.
 *      A reader token signed with the staff secret is a forgery waiting for
 *      one claims-validation bug; separate secrets make it cryptographically
 *      impossible rather than logically unlikely.
 *   3. **An explicit audience.** `aud: 'reader'`, refused by the staff
 *      verifier. Defence in depth for the day someone reuses a secret.
 *
 * **No role claim, deliberately.** A reader does not have one. Adding a
 * nullable `role` for symmetry would invite a `role === undefined` check
 * somewhere downstream that reads absence as permission.
 */

import { audienceMatches, decodeToken, encodeToken } from './token.ts'

/**
 * Thirty days.
 *
 * Much longer than the staff token's eight hours, and that asymmetry is the
 * point. The staff TTL is short because the token carries a *copy of the
 * roles*, so every second of it is a second a revoked editor keeps access.
 * A reader token carries no authority beyond "this is who you are" — there is
 * nothing to revoke — and signing a reader out every eight hours would be an
 * expensive way to protect nothing.
 *
 * Deletion is handled by `identities.status`, which is read on use, not
 * carried in the token.
 */
export const READER_SESSION_TTL_SECONDS = 60 * 60 * 24 * 30

export type ReaderSessionClaims = {
  /** `engine.identities.id` — a uuid, unlike the staff token's numeric id. */
  identityId: string
  email: string
  /** Unix seconds. */
  exp: number
  aud: 'reader'
}

export type ReaderVerifyFailure = 'malformed' | 'bad_signature' | 'expired' | 'wrong_audience'

export type ReaderVerifyResult =
  | { ok: true; claims: ReaderSessionClaims }
  | { ok: false; reason: ReaderVerifyFailure }

export function issueReaderToken(
  claims: Omit<ReaderSessionClaims, 'exp' | 'aud'>,
  secret: string,
  options: { ttlSeconds?: number; now?: () => Date } = {},
): string {
  const now = options.now ?? (() => new Date())
  const ttl = options.ttlSeconds ?? READER_SESSION_TTL_SECONDS
  const full: ReaderSessionClaims = {
    ...claims,
    exp: Math.floor(now().getTime() / 1000) + ttl,
    aud: 'reader',
  }
  return encodeToken(full, secret)
}

export function verifyReaderToken(
  token: string,
  secret: string,
  options: { now?: () => Date } = {},
): ReaderVerifyResult {
  const decoded = decodeToken(token, secret)
  if (!decoded.ok) return { ok: false, reason: decoded.reason }

  const raw = decoded.claims
  // A staff token has `aud: 'staff'`, and one minted before E8.2 has none at
  // all — `audienceMatches` treats a missing audience as staff, so neither
  // can pass here. That asymmetry is safe in this direction only, which is
  // why it is spelled out in `token.ts` rather than inferred.
  if (!audienceMatches(raw, 'reader')) return { ok: false, reason: 'wrong_audience' }

  if (
    typeof raw.identityId !== 'string' ||
    raw.identityId.length === 0 ||
    typeof raw.email !== 'string' ||
    typeof raw.exp !== 'number'
  ) {
    return { ok: false, reason: 'malformed' }
  }
  const claims = raw as unknown as ReaderSessionClaims

  const now = options.now ?? (() => new Date())
  if (claims.exp * 1000 <= now().getTime()) {
    return { ok: false, reason: 'expired' }
  }

  return { ok: true, claims }
}

/**
 * `__Host-` is browser-enforced: the cookie is refused unless it is Secure,
 * path `/`, and carries no Domain — so a neighbouring subdomain cannot set or
 * overwrite it. That matters more here than for staff, because the reader
 * cookie is set on the same hostname that serves the admin.
 */
export const READER_SESSION_COOKIE = '__Host-now-reader'

export function readerCookieOptions(ttlSeconds = READER_SESSION_TTL_SECONDS) {
  return {
    httpOnly: true,
    secure: true,
    // `lax` rather than `strict`: a reader following a link to an article from
    // a newsletter or a search result should arrive signed in. `strict` would
    // show them a signed-out page and a second click to fix it.
    sameSite: 'lax' as const,
    path: '/',
    maxAge: ttlSeconds,
  }
}

/** Clearing is `maxAge: 0` with otherwise identical attributes, or the browser keeps it. */
export function readerCookieClearOptions() {
  return { ...readerCookieOptions(0), maxAge: 0 }
}
