/**
 * Is `value` a safe same-site path to send a reader back to?
 *
 * Two callers need this: `/account/login?next=…` (E8 added no return-path
 * support at all — signing in always landed on `/account`) and the Save
 * toggle's `returnTo` field, which a plain HTML form posts as an ordinary
 * string a reader's browser controls entirely.
 *
 * A hand-postable "where to send me" value is a classic open-redirect: if it
 * is trusted verbatim, a crafted link (`/account/login?next=https://evil.example`)
 * signs a reader in and then ships them to a site that is not this one, right
 * after they typed a password. So this accepts only a path that starts with
 * exactly one `/` and resolves to no origin at all when parsed — which is
 * what rules out an absolute URL (`https://…`), a protocol-relative one
 * (`//evil.example/…`, which a browser resolves against its own scheme) and
 * the backslash variant some browsers still fold into `//` (`/\evil.example`).
 *
 * No `server-only` import: this is pure string logic, exercised directly by
 * `test/internalPath.test.ts` the same way `lib/taste.ts` is.
 */
export function safeInternalPath(value: string | null | undefined): string | null {
  if (!value) return null
  if (!value.startsWith('/') || value.startsWith('//')) return null

  try {
    // Resolved against a fixed, made-up base: if the value carries its own
    // origin (absolute, protocol-relative, or a backslash trick a browser
    // treats as protocol-relative), the parsed result's origin will not be
    // the fixed base's own — that mismatch is the whole check.
    const resolved = new URL(value, 'http://internal.invalid')
    if (resolved.origin !== 'http://internal.invalid') return null
  } catch {
    return null
  }

  return value
}
