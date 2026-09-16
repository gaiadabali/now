/**
 * Site identity for the reader app.
 *
 * ARCHITECTURE.md §3.5: ONE app, instantiated per city, differentiated only
 * by env. Nothing under `src/` may contain a site name, slug literal or
 * hostname — `npm run lint:site-literals` enforces that mechanically.
 *
 * The authoritative source is the platform `sites` registry row
 * (`engine/packages/config` mirrors the same contract in Python). Until the
 * web app has a DB connection, the loader reads the same fields from the
 * per-site config file in `<slug>/site/site.config.json`, which is a subset
 * of that row. Swapping the body of `getSiteConfig()` for a registry read is
 * the only change that migration needs — every consumer is already typed
 * against the contract, not the file.
 */

import { readFile } from 'node:fs/promises'
import path from 'node:path'

export type NavItem = { label: string; href: string }
export type FooterColumn = { head: string; links: NavItem[] }

export type SiteConfig = {
  slug: string
  name: string
  hostname: string
  locale: string
  timezone: string
  currency: string
  tagline: string
  // `favicon`/`appleIcon` are the square marks the live sites serve; the
  // logo is a wide wordmark and is unreadable at 16px, so it is not a
  // substitute. Optional so a config row without them still validates.
  brand: { logo: string; logoAlt: string; favicon?: string; appleIcon?: string }
  /**
   * Real, published contact details — taken from each city's live site, not
   * invented. Optional and rendered only where present: nowbali.co.id
   * publishes no email address (it uses a form), so Bali has none here rather
   * than a plausible-looking guess.
   */
  contact?: {
    address?: string[]
    phone?: string[]
    editorial?: string
    sales?: string
  }
  /**
   * The city's podcast, where one exists. Bali publishes a real show; Jakarta
   * does not, so Jakarta has no key here and its page says so plainly rather
   * than advertising something that does not exist.
   */
  podcast?: { name: string; spotifyShowId?: string; url: string }
  nav: NavItem[]
  footer: FooterColumn[]
}

/**
 * Which city this process serves. There is no default city — an unset
 * SITE_SLUG is a deployment error, not something to guess at. `dev` in
 * .env.example picks one explicitly.
 */
function requireSlug(): string {
  const slug = process.env.SITE_SLUG
  if (!slug) {
    throw new Error(
      'SITE_SLUG is not set. This app serves exactly one city per process; ' +
        'see ARCHITECTURE.md §3.5 and .env.example.',
    )
  }
  return slug
}

let cached: SiteConfig | null = null

export async function getSiteConfig(): Promise<SiteConfig> {
  if (cached) return cached
  const slug = requireSlug()
  // Repo root is four levels up from engine/apps/web.
  const root = process.env.NOW_REPO_ROOT ?? path.resolve(process.cwd(), '../../..')
  const file = path.join(root, slug, 'site', 'site.config.json')
  const raw = await readFile(file, 'utf8')
  cached = JSON.parse(raw) as SiteConfig
  return cached
}
