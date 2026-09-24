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
/**
 * One band of the home page, from `engine.sites.home_rails`.
 *
 * `pins` is the desk's hand on the front page: article ids (this city's) that
 * lead the band in the order given, with the band's own automatic fill after
 * them. An id that no longer resolves to a published article is skipped, not
 * rendered as a hole — an unpublish must never break the home page.
 *
 * Band keys the home page understands (EDITION-2-PLAN.md §3): `lead`, `edit`,
 * `for-you`, `department:<section>`, `guides`, `latest`, `explore`. An unknown
 * key is ignored rather than rendered.
 */
export type HomeRail = { key: string; label?: string; note?: string; limit?: number; pins?: number[] }

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
 * The baked file for an arbitrary city, read fresh on every call.
 *
 * `loadFile()` above caches a single result forever, on purpose: this process
 * serves exactly one `SITE_SLUG` (§3.5) and the file cannot change under a
 * running container, so caching it for the process lifetime costs nothing.
 * The platform console (S5.1) is the one caller that breaks that assumption —
 * it shows every city's registry row against its own file from one process,
 * and a single unkeyed cache slot would serve the first city's file to every
 * other city's comparison. So this is a second, deliberately uncached read,
 * used only there. It throws on a missing file rather than swallowing the
 * error, because the console needs to tell "no config file for this site"
 * apart from "the file says X" — the caller decides what an ENOENT means.
 */
export async function loadSiteConfigFile(slug: string): Promise<SiteConfig> {
  const root = process.env.NOW_REPO_ROOT ?? path.resolve(process.cwd(), '../../..')
  const file = path.join(root, slug, 'site', 'site.config.json')
  const raw = await readFile(file, 'utf8')
  return JSON.parse(raw) as SiteConfig
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
 *
 * **Exported (S5.1)** so the platform console validates a write with the
 * exact function that decides what a read does with it. A second
 * implementation in the console — even one that means to agree — is the way
 * this specific bug happens: an editor saves something `navFrom` will later
 * reject, sees no error because the console's copy accepted it, and the
 * masthead silently keeps the old nav. One function, two callers.
 */
export function navFrom(value: unknown): NavItem[] | null {
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

/**
 * The subset of `brand` a registry row actually specifies — only the keys
 * that are present and non-empty strings. Unlike `navFrom`, there is no
 * wholesale valid/invalid verdict for brand marks: a row that sets `logo` but
 * not `favicon` is not malformed, it is a console that has governed one mark
 * and left the other to the file. That per-key nature is exactly what makes
 * "governed or falling back" ambiguous for a single yes/no the way it is not
 * for `nav` — so this returns the partial itself, and callers (the reader's
 * `brandFrom` below, and the console) each ask a different question about it.
 */
export function brandTokensFrom(value: unknown): Partial<SiteConfig['brand']> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return {}
  const t = value as Record<string, unknown>
  const str = (k: string): string | undefined => (typeof t[k] === 'string' && t[k] !== '' ? (t[k] as string) : undefined)
  const out: Partial<SiteConfig['brand']> = {}
  const logo = str('logo')
  if (logo) out.logo = logo
  const logoAlt = str('logoAlt')
  if (logoAlt) out.logoAlt = logoAlt
  const favicon = str('favicon')
  if (favicon) out.favicon = favicon
  const appleIcon = str('appleIcon')
  if (appleIcon) out.appleIcon = appleIcon
  return out
}

function brandFrom(value: unknown, fallback: SiteConfig['brand']): SiteConfig['brand'] {
  return { ...fallback, ...brandTokensFrom(value) }
}

/**
 * **Exported (S5.1)**, for the same reason as `navFrom` above: the console
 * validates a `home_rails` write with the function that decides what a read
 * does with it, not a second guess at the same shape.
 */
export function railsFrom(value: unknown): HomeRail[] | null {
  if (!Array.isArray(value) || value.length === 0) return null
  const rails = value.filter(
    (r): r is HomeRail =>
      typeof r === 'object' &&
      r !== null &&
      typeof (r as HomeRail).key === 'string' &&
      (r as HomeRail).key !== '' &&
      ((r as HomeRail).pins === undefined ||
        (Array.isArray((r as HomeRail).pins) &&
          (r as HomeRail).pins!.every((id) => Number.isInteger(id) && id > 0))),
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
 * What a city gets when it has a registry row and no baked config file.
 *
 * `logo` is the one field with no safe empty value — the masthead renders an
 * `<img>` at it — so the caller supplies whatever the registry's
 * `brand_tokens` holds and this only fills in around it. `tagline` and
 * `footer` are file-only fields with no registry column; empty means "render
 * nothing there", which every consumer already handles because Bali has no
 * contact email and Jakarta has no podcast.
 */
const REGISTRY_ONLY_DEFAULTS = {
  tagline: '',
  footer: [] as FooterColumn[],
}

/**
 * The registry over the file.
 *
 * **A registry failure is never a site failure.** The masthead, the nav, the
 * footer and `metadataBase` all come through here, on a layout that cannot be
 * prerendered — so an exception thrown in this function is a 500 on every
 * page of the site, including the ones that need no database at all. The
 * catch is therefore deliberate and broad, and it logs rather than rethrows.
 * Falling back to the baked file yields the site exactly as it renders today.
 *
 * **And a MISSING FILE is no longer a site failure either.** It was, until
 * S5.1: `loadFile()` was awaited outside the try below, so an absent
 * `site.config.json` threw uncaught and took every route with it. That was
 * latent while the only cities were the two whose files the image bakes in —
 * and S5.1 is what makes it reachable, because a console that can register
 * and govern a city is a console that can produce a city with a registry row
 * and no file in the repo. §3.5 promises "adding a city is one command plus
 * config"; a 500 on every page is not what that should mean.
 *
 * So the two sources are now independently optional, and only losing BOTH is
 * fatal — which it should be, loudly, because there is then nothing to serve.
 */
export async function getSiteConfig(): Promise<SiteConfig> {
  const now = Date.now()
  if (cached && now - cached.at < REGISTRY_TTL_MS) return cached.value

  const slug = requireSlug()

  let file: SiteConfig | null = null
  try {
    file = await loadFile(slug)
  } catch (err) {
    // Not downgraded to a warning: for the two cities that ship a file this
    // means the image was built wrong, and it should be obvious in the log
    // even though the site keeps serving.
    console.error(`[site] no baked config file for "${slug}" — serving the registry row alone.`, err)
  }

  let row: RegistryRow | null = null
  try {
    row = await loadRegistry(slug)
  } catch (err) {
    // Once per TTL window at worst, so this cannot flood the log.
    console.error('[site] platform registry unreachable — serving the baked config file.', err)
  }

  if (!file && !row) {
    throw new Error(
      `No configuration for site "${slug}": there is no baked ` +
        `<slug>/site/site.config.json and no reachable engine.sites row. One or the other has ` +
        'to exist — see ARCHITECTURE.md §3.5 and docs/SURFACES-PLAN.md S1.3.',
    )
  }

  let value: SiteConfig

  if (file && row) {
    value = {
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
  } else if (row) {
    // Registry only. `brandFrom` needs a fallback for `logo`, and there is no
    // file to take one from, so an empty mark is passed in and the registry's
    // own `brand_tokens` fills it. A city governed here with no logo set
    // renders a broken image — which is visible, fixable in the console, and
    // better than the 500 this branch replaces.
    value = {
      ...REGISTRY_ONLY_DEFAULTS,
      slug,
      name: scalar(row.name, slug),
      hostname: scalar(row.hostname, ''),
      locale: scalar(row.locale, 'en'),
      timezone: scalar(row.timezone, 'UTC'),
      currency: scalar(row.currency, ''),
      brand: brandFrom(row.brand_tokens, { logo: '', logoAlt: scalar(row.name, slug) }),
      nav: navFrom(row.nav) ?? [],
      homeRails: railsFrom(row.home_rails) ?? undefined,
    }
  } else {
    value = file as SiteConfig
  }

  cached = { at: now, value }
  return value
}
