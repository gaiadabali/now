import { notFound } from 'next/navigation'

import { getSiteConfig } from '@/lib/site'
import type { SiteConfig } from '@/lib/site'

export { MODULES, MODULE_LIST, MODULE_LABELS, isModuleName } from '@/lib/moduleNames'
export type { ModuleName } from '@/lib/moduleNames'
import { MODULE_LABELS } from '@/lib/moduleNames'
import type { ModuleName } from '@/lib/moduleNames'

/**
 * P0.3 — `engine.sites.enabled_modules`, read on the web side.
 *
 * The column and the Python reader (`now_config.SiteConfig.has_module()`,
 * `engine/packages/config`) already exist (docs/ITINERARY-AND-READER-
 * PRODUCTS-PLAN.md §12's P0.3 row, §"Phase 0 — shipped"). This file is the
 * other half: the two guards every route/action Phases 1-6 add is expected
 * to call. The module *names* live in `lib/moduleNames.ts` — imported here
 * and re-exported, so every caller still writes `from '@/lib/modules'` and
 * there is exactly one place that spells `'partner_portal'` as a string.
 *
 * **Why a flag per feature, not a release branch.** §11a moved the partner
 * portal up and left the payment gateway "not decided" — several of these
 * modules will ship code before the business decision behind them is final.
 * A flag means that code can merge and sit off in production rather than
 * blocking on a decision this ticket does not make. Toggling one on is a
 * `/team-editor/platform/sites` write, live within `getSiteConfig()`'s
 * existing TTL — no deploy.
 *
 * **Local defaults are OFF.** Neither city's `engine.sites.enabled_modules`
 * row names any of these (`{feed,search,events}` only, confirmed against
 * `now_platform` in this worktree) — nothing here changes that, on purpose:
 * a module flips on only through an explicit console toggle, or
 * `UPDATE engine.sites SET enabled_modules = enabled_modules || '{print}'`.
 * See docs/ui-data-layer.md "Site config & module flags" for the local
 * toggle recipe.
 */

/**
 * Whether `site` has `module` on — the one predicate every gate below and
 * every dashboard panel calls, mirroring `now_config.SiteConfig.has_module()`
 * on the Python side so both readings of the same column agree by
 * construction rather than by two people remembering to keep two checks in
 * sync.
 */
export function moduleEnabled(site: Pick<SiteConfig, 'enabledModules'>, module: ModuleName): boolean {
  return site.enabledModules.includes(module)
}

/**
 * The gate for a server component or a route handler (`page.tsx`,
 * `layout.tsx`, `route.ts`): 404 when the module is off, exactly like
 * `accountsEnabled()` + `notFound()` in every `(site)/account` route
 * (`lib/reader.ts`, F141) — a reader gets the same "this does not exist"
 * response a route that was never built would give, rather than a page that
 * half-renders or explains itself into inviting a retry.
 *
 * Reads the current process's `getSiteConfig()` itself (this app serves one
 * `SITE_SLUG` per process — `lib/site.ts`), so a caller needs nothing more
 * than the module name:
 *
 * ```ts
 * export default async function ItineraryPage() {
 *   await requireModule(MODULES.itineraries)
 *   // ...
 * }
 * ```
 *
 * `site` is an optional override, taken for the same reason
 * `requireModuleForAction` below takes one: it lets a unit test assert the
 * gate's behaviour against a fixed `enabledModules` array without a
 * reachable platform database. Every real caller omits it.
 */
export async function requireModule(
  module: ModuleName,
  site?: Pick<SiteConfig, 'enabledModules'>,
): Promise<void> {
  const config = site ?? (await getSiteConfig())
  if (!moduleEnabled(config, module)) notFound()
}

/**
 * The result shape every gated server action returns instead of throwing —
 * `notFound()` renders Next's 404 boundary, which is right for a page but
 * wrong for a POST a form is mid-submit to: the caller has no page to
 * replace, only a notice to show, matching `PlatformActionResult`
 * (`team-editor/platform/sites/[slug]/actions.ts`) and every other reader
 * server action's `{ ok, message }` return.
 */
export type ModuleGateResult = { ok: false; message: string }

function moduleOffMessage(module: ModuleName): string {
  return `${MODULE_LABELS[module]} is not available on this site yet.`
}

/**
 * The server-action counterpart to `requireModule()`. Returns `null` when
 * the module is on (nothing to report — proceed), or the `{ ok: false,
 * message }` to return from the action as-is when it is off:
 *
 * ```ts
 * export async function saveItineraryDay(...): Promise<PlatformActionResult> {
 *   const gate = await requireModuleForAction(MODULES.itineraries)
 *   if (gate) return gate
 *   // ...
 * }
 * ```
 *
 * `site`: same optional test override as `requireModule`.
 */
export async function requireModuleForAction(
  module: ModuleName,
  site?: Pick<SiteConfig, 'enabledModules'>,
): Promise<ModuleGateResult | null> {
  const config = site ?? (await getSiteConfig())
  if (moduleEnabled(config, module)) return null
  return { ok: false, message: moduleOffMessage(module) }
}
