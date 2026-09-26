/**
 * The loader `verify-module-flags.mjs` registers: `alias-loader.mjs`'s `@/*`
 * rewrite, plus one extra rule that redirects the bare `next/navigation`
 * specifier to `stub-next-navigation.mjs` — see that file for why the real
 * one cannot be loaded from plain Node at all, not even with `--conditions
 * react-server`.
 */
import { resolve as resolveAlias } from './alias-loader.mjs'

const STUB = new URL('./stub-next-navigation.mjs', import.meta.url)

export async function resolve(specifier, context, nextResolve) {
  if (specifier === 'next/navigation') {
    return nextResolve(STUB.href, context)
  }
  return resolveAlias(specifier, context, nextResolve)
}
