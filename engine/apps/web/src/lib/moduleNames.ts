/**
 * The `engine.sites.enabled_modules` vocabulary (P0.3) — names only, no
 * imports, so both `lib/site.ts` (`modulesFrom`, the read side) and
 * `lib/modules.ts` (the gates) depend on this one file instead of on each
 * other. See `lib/modules.ts` for the gates themselves and why this list
 * exists at all.
 */
export const MODULES = {
  itineraries: 'itineraries',
  reading: 'reading',
  print: 'print',
  offers: 'offers',
  newsletter: 'newsletter',
  partnerPortal: 'partner_portal',
} as const

export type ModuleName = (typeof MODULES)[keyof typeof MODULES]

/** Every known module, in the fixed order the platform admin screen shows them. */
export const MODULE_LIST: ModuleName[] = [
  MODULES.itineraries,
  MODULES.reading,
  MODULES.print,
  MODULES.offers,
  MODULES.newsletter,
  MODULES.partnerPortal,
]

export const MODULE_LABELS: Record<ModuleName, string> = {
  itineraries: 'Itineraries',
  reading: 'Reading state (Continue reading / Saved history)',
  print: 'Print edition & subscriptions',
  offers: 'Partner offers & vouchers',
  newsletter: 'Newsletter',
  partner_portal: 'Partner portal',
}

export function isModuleName(value: unknown): value is ModuleName {
  return typeof value === 'string' && (MODULE_LIST as string[]).includes(value)
}

/**
 * The array `saveModules` writes back to `engine.sites.enabled_modules`.
 *
 * The column is shared: it already holds `{feed,search,events}` on both
 * cities (read by nothing on the web side, but they are the Python side's
 * `has_module()` vocabulary), and the platform admin screen only owns the
 * six names above. So a save keeps every entry of `current` that is NOT one
 * of ours, in its original order, then appends the selected P0.3 modules in
 * `MODULE_LIST` order. Anything in `selected` that is not a known module name
 * is dropped; duplicates collapse.
 */
export function mergeModuleSelection(current: readonly string[] | null | undefined, selected: unknown): string[] {
  const kept = (current ?? []).filter((entry) => !isModuleName(entry))
  const chosen = new Set(Array.isArray(selected) ? selected.filter(isModuleName) : [])
  const ours = MODULE_LIST.filter((module) => chosen.has(module))
  return [...new Set([...kept, ...ours])]
}
