/**
 * Site identity for the reader app.
 *
 * ARCHITECTURE.md §3.5: ONE app, instantiated per city, differentiated only
 * by env. Nothing under `src/` may contain a site name, slug literal or
 * hostname — `npm run lint:site-literals` enforces that mechanically.
 *
 * **S1.3 — this now reads the platform `sites` registry, with the baked
 * config file underneath it.** The previous version of this comment said the
 * registry row was "the authoritative source" and then read only the file,
 * and promised that swapping the body of `getSiteConfig()` was "the only
 * change that migration needs". That promise held: every consumer was
 * already typed against the contract rather than the file, and no page
 * changed.
 *
 * Why it mattered enough to do first: `engine.sites` carries `nav`,
 * `brand_tokens`, `home_rails` and `ranking_weights` precisely so that a
 * console can govern them, and nothing read any of them. A platform console
 * that cannot change what a reader sees is a set of tables with a login on
 * it. This is the seam that makes S5 a console instead of a report.
 *
 * **The file is not legacy and is not going away.** It stays as the floor
 * under the registry, for three reasons, in order of how badly each would
 * hurt: the platform database being unreachable must degrade to a correct
 * masthead rather than to no masthead; the file carries fields the registry
 * has no column for (`tagline`, `contact`, `podcast`, `footer`); and a city
 * whose registry row has never been touched by the console renders exactly
 * as it does today, which is what makes this change safe to deploy before
 * the console exists to drive it.
 */

import { readFile } from 'node:fs/promises'
import path from 'node:path'

import { platformConnectionString, query } from '@/lib/db'

export type NavItem = { label: string; href: string }
export type FooterColumn = { head: string; links: NavItem[] }

/**
 * One rail on the homepage, as the registry describes it.
 *
 * `key` names which rail — the homepage owns what each one means and how it
 * is laid out; the registry owns which appear and in what order. That split
 * is deliberate: a console that could define arbitrary rails would need to
 * describe queries, and `ranking_weights` is already the column for
 * influencing what the engine returns. This is presentation order, nothing
 * more.
 *
 * `label` and `note` override the headings the homepage hardcodes today, so
 * an editor can retitle "The Edit" without a deploy. Both optional: an
 * absent label means the rail keeps its built-in one.
 *
 * Nothing reads this yet. It is defined here because S1.3's job is the seam,
 * and a typed empty seam is what lets S6.3 be a homepage change rather than a
 * homepage change plus a contract negotiation.
 */
export type HomeRail = { key: string; label?: string; note?: string; limit?: number }

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
  /**
   * Homepage rail order, from `engine.sites.home_rails`. Registry-only —
   * there is no field for it in the config file, and `undefined` means the
   * homepage uses its own built-in order, which is what it does today.
   */
  homeRails?: HomeRail[]
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

/**
 * The baked file, read once per process.
 *
 * Still process-lifetime rather than TTL'd: this file is COPYed into the
 * image (`apps/web/Dockerfile`, `NOW_REPO_ROOT=/app/sites`), so it cannot
 * change under a running container. Re-reading it would be a syscall per
 * request in exchange for nothing.
 */
let fileCached: SiteConfig | null = null

async function loadFile(slug: string): Promise<SiteConfig> {
  if (fileCached) return fileCached
  // Repo root is four levels up from engine/apps/web.
  const root = process.env.NOW_REPO_ROOT ?? path.resolve(process.cwd(), '../../..')
  const file = path.join(root, slug, 'site', 'site.config.json')
  const raw = await readFile(file, 'utf8')
  fileCached = JSON.parse(raw) as SiteConfig
  return fileCached
}

/**
 * How long a console edit may take to reach readers.
 *
 * The registry read cannot be process-lifetime cached the way the file is —
 * that is the whole difference between the two sources, and caching it
 * forever would reproduce exactly the problem this change exists to fix: an
 * editor changes the nav in the console and nothing happens until someone
 * redeploys.
 *
 * 30 seconds is chosen against the two costs it sits between. Lower means a
 * query per render on a `force-dynamic` layout that runs on every page of the
 * site. Higher means an editor changes the masthead, reloads, sees the old
 * one, and reasonably concludes the console is broken. Half a minute is
 * inside the time it takes to switch tabs and look.
 */
const REGISTRY_TTL_MS = Number(process.env.SITE_CONFIG_TTL_MS ?? 30_000)

type RegistryRow = {
  name: string | null
  hostname: string | null
  locale: string | null
  timezone: string | null
  currency: string | null
  nav: unknown
  brand_tokens: unknown
  home_rails: unknown
}

/**
 * `{}` is not an empty nav — it is an absent one.
 *
 * Every jsonb column on `engine.sites` is `NOT NULL DEFAULT '{}'::jsonb`, so
 * an ungoverned row holds an empty *object* where a populated one holds an
 * array. A reader that treated `{}` as "zero nav items" would render a site
 * with no navigation at all, on every city whose registry row nobody has
 * touched — which today is all of them. So each field is shape-checked and
 * anything unrecognised falls back to the file rather than being coerced.
 */
function navFrom(value: unknown): NavItem[] | null {
  if (!Array.isArray(value) || value.length === 0) return null
  const items = value.filter(
    (i): i is NavItem =>
      typeof i === 'object' &&
      i !== null &&
      typeof (i as NavItem).label === 'string' &&
      typeof (i as NavItem).href === 'string' &&
      (i as NavItem).label !== '' &&
      (i as NavItem).href !== '',
  )
  // All-or-nothing: a partially valid nav would silently drop the section a
  // console typo landed in, and a missing section is harder to notice than a
  // nav that plainly did not change.
  return items.length === value.length ? items : null
}

function brandFrom(value: unknown, fallback: SiteConfig['brand']): SiteConfig['brand'] {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return fallback
  const t = value as Record<string, unknown>
  const str = (k: string): string | undefined => (typeof t[k] === 'string' && t[k] !== '' ? (t[k] as string) : undefined)
  return {
    logo: str('logo') ?? fallback.logo,
    logoAlt: str('logoAlt') ?? fallback.logoAlt,
    favicon: str('favicon') ?? fallback.favicon,
    appleIcon: str('appleIcon') ?? fallback.appleIcon,
  }
}

function railsFrom(value: unknown): HomeRail[] | null {
  if (!Array.isArray(value) || value.length === 0) return null
  const rails = value.filter(
    (r): r is HomeRail =>
      typeof r === 'object' && r !== null && typeof (r as HomeRail).key === 'string' && (r as HomeRail).key !== '',
  )
  return rails.length === value.length ? rails : null
}

/** A non-empty string wins over the file; anything else does not. */
const scalar = (v: string | null | undefined, fallback: string): string =>
  typeof v === 'string' && v.trim() !== '' ? v : fallback

async function loadRegistry(slug: string): Promise<RegistryRow | null> {
  if (!platformConnectionString()) return null
  const rows = await query<RegistryRow>(
    `SELECT name, hostname, locale, timezone, currency, nav, brand_tokens, home_rails
       FROM engine.sites
      WHERE slug = $1 AND status <> 'disabled'
      LIMIT 1`,
    [slug],
  )
  return rows[0] ?? null
}

let cached: { at: number; value: SiteConfig } | null = null

/**
 * The registry over the file.
 *
 * **A registry failure is never a site failure.** The masthead, the nav, the
 * footer and `metadataBase` all come through here, on a layout that cannot be
 * prerendered — so an exception thrown in this function is a 500 on every
 * page of the site, including the ones that need no database at all. The
 * catch is therefore deliberate and broad, and it logs rather than rethrows.
 * Falling back to the baked file yields the site exactly as it renders today.
 */
export async function getSiteConfig(): Promise<SiteConfig> {
  const now = Date.now()
  if (cached && now - cached.at < REGISTRY_TTL_MS) return cached.value

  const slug = requireSlug()
  const file = await loadFile(slug)

  let row: RegistryRow | null = null
  try {
    row = await loadRegistry(slug)
  } catch (err) {
    // Once per TTL window at worst, so this cannot flood the log.
    console.error('[site] platform registry unreachable — serving the baked config file.', err)
  }

  const value: SiteConfig = row
    ? {
        ...file,
        name: scalar(row.name, file.name),
        hostname: scalar(row.hostname, file.hostname),
        locale: scalar(row.locale, file.locale),
        timezone: scalar(row.timezone, file.timezone),
        currency: scalar(row.currency, file.currency),
        nav: navFrom(row.nav) ?? file.nav,
        brand: brandFrom(row.brand_tokens, file.brand),
        // Registry-only: there is no column-less equivalent in the file, and
        // an absent value means "the homepage decides", which is what it does
        // today. S6.3 is what starts reading this.
        homeRails: railsFrom(row.home_rails) ?? undefined,
      }
    : file

  cached = { at: now, value }
  return value
}
