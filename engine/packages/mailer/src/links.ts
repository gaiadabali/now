/**
 * Building the links that go in transactional mail.
 *
 * This file is small and load-bearing. A verification or reset link is a
 * bearer credential: whoever opens it is treated as the account holder. So the
 * question "which host does the link point at" is a security question, not a
 * formatting one.
 *
 * ## Host-header injection, and why the base URL is configuration
 *
 * The obvious implementation reads the incoming request's `Host` header and
 * builds the link from it. That is a real, routinely exploited vulnerability:
 * an attacker POSTs a password-reset for someone else's address with
 * `Host: attacker.example`, the victim gets a genuine-looking mail from the
 * real system, clicks it, and hands their single-use reset token to the
 * attacker's server. The mail is authentic — that is what makes it work.
 *
 * `Host` is attacker-controlled input. `X-Forwarded-Host` doubly so. Neither
 * is ever consulted here. The base URL comes from configuration, and a site
 * whose base URL is not configured cannot send links at all — which is a
 * startup error, not a silent fallback to whatever the proxy said.
 */

export type LinkFailure = 'unconfigured_base' | 'invalid_base' | 'insecure_base'

export type LinkResult = { ok: true; url: string } | { ok: false; reason: LinkFailure }

export type LinkOptions = {
  /** Allow http:// — for local development only. */
  allowInsecure?: boolean
}

/**
 * `base` must be an absolute origin from configuration. `path` is ours.
 * `params` are appended with proper encoding; a token goes here, never
 * interpolated into `path` by the caller.
 */
export function buildLink(
  base: string | undefined,
  path: string,
  params: Record<string, string> = {},
  options: LinkOptions = {},
): LinkResult {
  if (!base?.trim()) return { ok: false, reason: 'unconfigured_base' }

  let url: URL
  try {
    // Two-argument URL would let a caller's absolute `path` silently replace
    // the configured origin, which is the exact substitution this module
    // exists to prevent. Parse the base alone, then attach our path to it.
    url = new URL(base)
  } catch {
    return { ok: false, reason: 'invalid_base' }
  }

  if (url.protocol !== 'https:' && url.protocol !== 'http:') {
    return { ok: false, reason: 'invalid_base' }
  }
  // A token travelling over http is a token on the wire. Permitted only when
  // a caller has explicitly said this is a development environment.
  if (url.protocol === 'http:' && !options.allowInsecure) {
    return { ok: false, reason: 'insecure_base' }
  }

  // Join without letting a leading slash reset the path, and without
  // producing a double slash.
  const basePath = url.pathname.replace(/\/+$/, '')
  const tail = path.replace(/^\/+/, '')
  url.pathname = `${basePath}/${tail}`

  // `search` is rebuilt rather than appended to, so a base URL that arrived
  // carrying a query string cannot smuggle a parameter — `?token=` from the
  // configured base losing to ours, or winning, depending on read order.
  url.search = ''
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, value)
  }
  url.hash = ''

  return { ok: true, url: url.toString() }
}
