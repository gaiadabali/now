/**
 * The city's brand marks, for the admin chrome.
 *
 * ARCHITECTURE.md §3.5: ONE image per city, differentiated only by env. The
 * admin is served by the reader app under the city's own hostname
 * (docs/ADMIN-CONSOLIDATION.md Phase 2), so an editor who has both cities
 * open has two identical tabs unless the chrome says which is which. The
 * logo is that signal — and it is the client's own mark, not Payload's.
 *
 * WHY THIS DUPLICATES ~20 LINES OF `apps/web/src/lib/site.ts`.
 * The dependency runs one way: the web app imports this package's Payload
 * config, never the reverse. A component registered in `admin.components`
 * is resolved by Payload out of *this* package, so it cannot reach for the
 * web app's `@/lib/site`. The alternative — a fourth workspace package for
 * twenty lines — buys less than it costs. What is shared is the *file*:
 * both readers parse the same `<slug>/site/site.config.json`, which is the
 * contract that actually matters. Only the brand fields are typed here;
 * the rest of the row is the reader app's business.
 *
 * Degradation is deliberate. No SITE_SLUG, no config file, no `brand` key:
 * every one of those returns `null` and the components fall back to a plain
 * wordmark. An admin whose logo is missing is a cosmetic problem; an admin
 * that throws on boot because a JSON file moved is an outage.
 */

import { readFile } from 'node:fs/promises'
import path from 'node:path'

export type SiteBrand = {
  /** Display name, e.g. for the logo's alt text when the config gives none. */
  name: string
  /**
   * The bare city slug — added for `SurfaceKicker`, which needs just the
   * city word ("TEAM EDITOR · {city}") rather than the full display name
   * ("NOW! {city}") the rail's own wordmark already shows a few pixels
   * above it. No literal city name lives in this file — see this package's
   * own `lint:site-literals`, which bans the word anywhere in source,
   * including comments describing it.
   */
  slug: string | null
  /** Wide wordmark. Unreadable at 16px — see `icon`. */
  logo: string
  logoAlt: string
  /**
   * The square mark. `favicon` in the config, which is exactly this: the
   * mark the live sites already serve at 16–32px. Falls back to nothing
   * rather than to `logo`, because a squashed wordmark reads as a bug.
   */
  icon: string | null
}

/**
 * Where the city config directories live. The web image bakes them at
 * `/app/sites` and sets this (see apps/web/Dockerfile); in a dev checkout
 * it is the repo root, which we find by walking up from the working
 * directory rather than counting `..` — the count differs between
 * `apps/web` and `packages/cms`, and a wrong count fails silently.
 */
async function resolveConfigFile(slug: string): Promise<string | null> {
  const explicit = process.env.NOW_REPO_ROOT
  const rel = path.join(slug, 'site', 'site.config.json')
  if (explicit) return path.join(explicit, rel)

  let dir = process.cwd()
  for (let depth = 0; depth < 6; depth++) {
    const candidate = path.join(dir, rel)
    try {
      await readFile(candidate, 'utf8')
      return candidate
    } catch {
      const parent = path.dirname(dir)
      if (parent === dir) break
      dir = parent
    }
  }
  return null
}

// Resolved once per process. The config is baked into the image, so it
// cannot change under a running container — re-reading it per render would
// be a filesystem hit on every admin page for a value that never moves.
let cached: SiteBrand | null | undefined

export async function loadSiteBrand(): Promise<SiteBrand | null> {
  if (cached !== undefined) return cached

  const slug = process.env.SITE_SLUG
  if (!slug) {
    cached = null
    return cached
  }

  try {
    const file = await resolveConfigFile(slug)
    if (!file) throw new Error(`no site.config.json found for slug "${slug}"`)
    const raw = JSON.parse(await readFile(file, 'utf8')) as {
      name?: string
      brand?: { logo?: string; logoAlt?: string; favicon?: string }
    }
    const logo = raw.brand?.logo
    if (!logo) throw new Error('site config has no brand.logo')

    cached = {
      name: raw.name ?? 'NOW!',
      // `slug` is `process.env.SITE_SLUG` itself, not a field read back out of
      // the JSON — the env var is what selected this file in the first place,
      // so it is already the trusted value and re-reading it from the parsed
      // config would just be asking the same question twice.
      slug,
      logo,
      logoAlt: raw.brand?.logoAlt ?? raw.name ?? 'NOW!',
      icon: raw.brand?.favicon ?? null,
    }
  } catch (error) {
    // Loud, once, at first render — not per request, since the result is
    // cached either way.
    console.error('[cms] site brand unavailable; admin falls back to a plain wordmark:', error)
    cached = null
  }

  return cached
}
