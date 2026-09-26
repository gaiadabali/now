'use server'

import { revalidatePath } from 'next/cache'

import { requireStaffAdmin } from '@/lib/auth'
import { mergeModuleSelection } from '@/lib/moduleNames'
import type { ModuleName } from '@/lib/moduleNames'
import {
  getRegistrySite,
  updateSiteBrandTokens,
  updateSiteEnabledModules,
  updateSiteHomeRails,
  updateSiteNav,
} from '@/lib/queries'
import { brandTokensFrom, modulesFrom, navFrom, railsFrom } from '@/lib/site'
import type { HomeRail, NavItem, SiteConfig } from '@/lib/site'

import { PLATFORM_ROOT, siteHref } from '../../paths'

/**
 * The write half of S5.1 — the whole reason this ticket exists.
 *
 * **`requireStaffAdmin()` is the first line of every export, not once in a
 * layout.** A server action is its own POST endpoint, reachable by anyone who
 * has ever loaded the page that renders its form — a guard on the page
 * protects the reading, and does nothing for the action
 * (`team-editor/staff/actions.ts` makes the same argument; this file follows
 * it exactly). Editorial `admin` and commerce `admin` are both insufficient
 * here on purpose: this is platform-wide configuration, one level above
 * either dimension in `docs/ADMIN-CONSOLIDATION.md`'s split, so the same gate
 * that mints staff accounts is the one that governs what every reader sees.
 *
 * **Validation reuses `lib/site.ts`'s own predicates, not a second guess at
 * them.** `navFrom` / `brandTokensFrom` / `railsFrom` are exactly what
 * `getSiteConfig()` runs a registry row through on every render. If this file
 * accepted something those reject, the failure mode is the worst one this
 * screen can produce: the editor sees "saved", reloads the reader site, and
 * the masthead has not changed — with nothing on screen explaining why. So
 * every save runs the submitted value through the real validator before
 * writing, and refuses if it comes back `null`, with a message that says
 * which item is the problem rather than just "invalid".
 */

export type PlatformActionResult = { ok: boolean; message: string }

/**
 * A friendlier first pass than "rejected" — `navFrom` is all-or-nothing and
 * says nothing about *which* item sank it. This exists only to write a
 * message a human can act on; `navFrom` itself, called further down, is the
 * actual authority on whether the save proceeds.
 */
function describeNavProblem(nav: NavItem[]): string | null {
  if (nav.length === 0) {
    return 'Add at least one item. An empty nav is not the same as leaving this ungoverned — it would render the site with no navigation at all, where an untouched row falls back to the config file instead.'
  }
  const badIndex = nav.findIndex((item) => !item?.label?.trim() || !item?.href?.trim())
  if (badIndex !== -1) {
    return `Item ${badIndex + 1} is missing a label or a link. Every item needs both — one incomplete item rejects the whole nav on read, and the site keeps whatever it had before.`
  }
  return null
}

export async function saveNav(slug: string, nav: NavItem[]): Promise<PlatformActionResult> {
  const actor = await requireStaffAdmin()

  const site = await getRegistrySite(slug)
  if (!site) return { ok: false, message: 'That site no longer exists.' }

  const problem = describeNavProblem(nav)
  if (problem) return { ok: false, message: problem }

  // The real gate. If this and `describeNavProblem` above ever disagree,
  // this is the one that decides what gets written — it is the same
  // function `getSiteConfig()` calls.
  const validated = navFrom(nav)
  if (!validated) {
    return {
      ok: false,
      message: 'That nav was rejected on validation. Check that every item has both a label and a link.',
    }
  }

  await updateSiteNav(slug, validated)
  console.info('[platform] %s set nav for %s (%d item(s))', actor.email, slug, validated.length)
  revalidatePath(siteHref(slug))
  revalidatePath(PLATFORM_ROOT)
  return { ok: true, message: `Saved ${validated.length} nav item(s) for ${site.name}. Live within 30 seconds.` }
}

/**
 * No "refuse empty" rule here, unlike `saveNav` — and that asymmetry is
 * deliberate, not an oversight. Clearing every brand field writes `{}`, which
 * reverts fully to the file's marks: a real, fully-functional state, not a
 * blank one. Nav has no such safe empty; brand does.
 */
export async function saveBrand(slug: string, brand: Partial<SiteConfig['brand']>): Promise<PlatformActionResult> {
  const actor = await requireStaffAdmin()

  const site = await getRegistrySite(slug)
  if (!site) return { ok: false, message: 'That site no longer exists.' }

  // Running the submission through the reader's own extraction before
  // writing means the column only ever holds keys `brandFrom` will actually
  // honour — never, say, a non-string value a client-side bug let through.
  const validated = brandTokensFrom(brand)
  await updateSiteBrandTokens(slug, validated)

  const count = Object.keys(validated).length
  console.info('[platform] %s set brand_tokens for %s (%d field(s) governed)', actor.email, slug, count)
  revalidatePath(siteHref(slug))
  revalidatePath(PLATFORM_ROOT)
  return {
    ok: true,
    message:
      count === 0
        ? `Cleared every brand mark for ${site.name} — it now reads entirely from the config file.`
        : `Saved ${count} brand mark(s) for ${site.name}. Live within 30 seconds.`,
  }
}

function describeRailsProblem(rails: HomeRail[]): string | null {
  const badIndex = rails.findIndex((rail) => !rail?.key?.trim())
  if (badIndex !== -1) {
    return `Rail ${badIndex + 1} has no key. Every rail needs one — one missing key rejects the whole order on read.`
  }
  return null
}

export async function saveHomeRails(slug: string, rails: HomeRail[]): Promise<PlatformActionResult> {
  const actor = await requireStaffAdmin()

  const site = await getRegistrySite(slug)
  if (!site) return { ok: false, message: 'That site no longer exists.' }

  if (rails.length === 0) {
    // Unlike `nav`, `home_rails` has no config-file fallback to speak of —
    // it is registry-only (`lib/site.ts`'s `SiteConfig.homeRails` comment).
    // An empty order and an untouched `{}` row mean the same thing to a
    // reader: "the homepage decides its own order", which is today's actual
    // behaviour and is not a blank page. So this is the one field S5.1 does
    // not refuse to save empty — clearing it is a real, intentional revert.
    await updateSiteHomeRails(slug, [])
    console.info('[platform] %s cleared home_rails for %s', actor.email, slug)
    revalidatePath(siteHref(slug))
    revalidatePath(PLATFORM_ROOT)
    return { ok: true, message: `Cleared the rail order for ${site.name} — the homepage will use its own default order.` }
  }

  const problem = describeRailsProblem(rails)
  if (problem) return { ok: false, message: problem }

  const validated = railsFrom(rails)
  if (!validated) {
    return { ok: false, message: 'That order was rejected on validation. Check that every rail has a key.' }
  }

  await updateSiteHomeRails(slug, validated)
  console.info('[platform] %s set home_rails for %s (%d item(s))', actor.email, slug, validated.length)
  revalidatePath(siteHref(slug))
  revalidatePath(PLATFORM_ROOT)
  return { ok: true, message: `Saved the rail order (${validated.length} item(s)) for ${site.name}.` }
}

/**
 * `enabled_modules` (P0.3) — the toggle screen for the flags `lib/modules.ts`'s
 * `moduleEnabled()`/`requireModule()` read. Same shape as the three writes
 * above: re-check `requireStaffAdmin()`, re-validate through the reader's own
 * predicate (`modulesFrom`, `lib/site.ts`) rather than trusting the checkbox
 * list the client sent, log the write, revalidate both this page and the
 * index.
 *
 * Entries that are not P0.3 module names (`feed`, `search`, `events`) are
 * preserved as-is — see `mergeModuleSelection` (`lib/moduleNames.ts`).
 *
 * No "refuse empty" rule, like `saveBrand` and unlike `saveNav` — turning
 * every module off is a real, intentional state (every new reader surface
 * ships dark until a console toggle turns it on), not a broken one.
 */
export async function saveModules(slug: string, modules: ModuleName[]): Promise<PlatformActionResult> {
  const actor = await requireStaffAdmin()

  const site = await getRegistrySite(slug)
  if (!site) return { ok: false, message: 'That site no longer exists.' }

  // The real gate — `getSiteConfig()` runs the column through this exact
  // function, so nothing can be written here that a reader would then
  // silently drop on the next request.
  const validated = modulesFrom(modules)

  // The column is shared with entries this screen does not own
  // (`{feed,search,events}`, the Python side's vocabulary) — replace only
  // the P0.3 part of it, never the whole array.
  const next = mergeModuleSelection(site.enabled_modules, validated)

  await updateSiteEnabledModules(slug, next)
  console.info(
    '[platform] %s set enabled_modules for %s: [%s]',
    actor.email,
    slug,
    next.join(', '),
  )
  revalidatePath(siteHref(slug))
  revalidatePath(PLATFORM_ROOT)
  return {
    ok: true,
    message:
      validated.length === 0
        ? `Cleared every module flag for ${site.name} — every new reader surface stays off.`
        : `Saved ${validated.length} module(s) for ${site.name}: ${validated.join(', ')}. Live within 30 seconds.`,
  }
}
