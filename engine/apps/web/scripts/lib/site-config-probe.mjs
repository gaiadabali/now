/**
 * Calls `getSiteConfig()` once and prints the result as one line of JSON.
 *
 * A separate process on purpose, and that is the whole reason this file
 * exists rather than a loop inside `verify-site-config.mjs`:
 * `getSiteConfig()` memoises its answer for the TTL and `loadFile()` memoises
 * for the process lifetime, so four fallback cases run in one process would
 * all read the first case's answer and pass for the wrong reason.
 *
 * Reads `NOW_REPO_ROOT`, `SITE_SLUG` and `PLATFORM_DATABASE_URL` from the
 * environment — the caller varies those to remove one source at a time.
 * Exits 1 when `getSiteConfig()` throws, which for this probe is a result
 * rather than a failure: one of the four cases expects it.
 */
import { register } from 'node:module'

register('./alias-loader.mjs', import.meta.url)

const { getSiteConfig } = await import('../../src/lib/site.ts')

try {
  const config = await getSiteConfig()
  console.log(
    JSON.stringify({
      ok: true,
      slug: config.slug,
      name: config.name,
      nav: config.nav.length,
      tagline: config.tagline,
      footer: config.footer.length,
      logo: config.brand.logo,
    }),
  )
  process.exit(0)
} catch (err) {
  console.log(JSON.stringify({ ok: false, error: String(err.message).split('\n')[0] }))
  process.exit(1)
}
