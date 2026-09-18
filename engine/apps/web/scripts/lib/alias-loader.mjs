/**
 * A Node ESM loader hook that resolves this app's `@/*` path alias.
 *
 * Next resolves `@/*` to `./src/*` via `tsconfig.json`'s `paths` — a bundler
 * concern that plain `node --test` knows nothing about. `lib/site.ts` imports
 * `@/lib/db` with that alias, so any script that wants to load the real
 * `lib/site.ts` — rather than a hand-copied reimplementation of it — needs
 * this resolved first. Used by `scripts/verify-site-config.mjs`; see that
 * file for why a script and not `test/*.test.ts`.
 */
const SRC = new URL('../../src/', import.meta.url)

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith('@/')) {
    // `SRC` is already a file:// URL, so appending the rest of the specifier
    // to it produces one too — no `pathToFileURL` round trip needed, and
    // passing one a URL object throws (it wants a plain path string).
    const target = new URL(`${specifier.slice(2)}.ts`, SRC)
    return nextResolve(target.href, context)
  }
  return nextResolve(specifier, context)
}
