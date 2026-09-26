/**
 * A stand-in for `next/navigation`'s `notFound()`, used only by
 * `scripts/verify-module-flags.mjs` (via `module-flags-loader.mjs`).
 *
 * The real `next/navigation` cannot be imported from plain Node at all: it
 * pulls in `next/dist/shared/lib/app-router-context.shared-runtime.js`,
 * which calls `React.createContext` — a client-graph API the `react-server`
 * condition `lib/db.ts`'s `server-only` import needs (see
 * `verify-module-flags.mjs`'s own docstring) deliberately removes from
 * `react`'s server build. There is no single `--conditions` value that
 * satisfies both `server-only` and `next/navigation` outside a real Next
 * compilation, which runs the server and client graphs through two
 * different webpack configurations precisely so each import resolves
 * against the right one.
 *
 * So this script does not attempt to reproduce Next's own module graph — it
 * substitutes the one function `lib/modules.ts`'s `requireModule()` calls
 * with a stand-in that throws a distinctive, recognisable error, and asserts
 * that `requireModule()` throws it exactly when the module is off and never
 * when it is on. That is the real contract: "off" ends in a call to
 * `notFound()`, not "off throws some error or other".
 */
export const NOT_FOUND_MARKER = 'NOW_VERIFY_NOT_FOUND_STUB'

export function notFound() {
  throw new Error(NOT_FOUND_MARKER)
}
