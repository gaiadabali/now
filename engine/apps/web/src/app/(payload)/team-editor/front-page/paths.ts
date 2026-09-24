import { DEFAULT_HOME_RAILS } from '@/lib/homeBands'

/**
 * Where the front-page editor lives. Same reasoning as every other
 * `paths.ts` beside it (`platform/paths.ts`, `staff/paths.ts`).
 */
export const FRONT_PAGE_ROOT = '/team-editor/front-page'
export const EDITOR_ROOT = '/team-editor'

/**
 * The seven band keys the home page understands (EDITION-2-PLAN.md §3).
 * `department:<section>` is a family, not one key — `DEPARTMENT_SECTIONS`
 * below names the sections this build knows about, mirrored from
 * `lib/payload.ts`'s `TYPE_TO_SECTION` values (deduplicated) rather than
 * imported from it: that file is the reader app's own data layer (owned by
 * WS1/WS2 for this workstream split) and this is an admin-only convenience
 * list for scaffolding a first, editable band order, not a second definition
 * of what a section IS. If the two ever disagree, the reader's own mapping
 * wins — this list only decides what the front-page editor offers to add.
 */
export const DEPARTMENT_SECTIONS = ['dining', 'stay', 'wellness', 'things-to-do', 'events', 'editorial'] as const

/** Where an editor starts when `home_rails` has never been saved: exactly
 * the order the home page renders in that state (`lib/homeBands.ts`), so the
 * first Save changes only what the editor changed. The other departments are
 * one "Add a band" away (`addableBandTypes`), not pre-stacked. */
export function defaultBandOrder(): string[] {
  return DEFAULT_HOME_RAILS.map((rail) => rail.key)
}

/**
 * "Raw band keys must never be the visible label" (DESIGN-SYSTEM.md §6 — say
 * what a thing does, in the reader's own words). `key` is stored and is the
 * one thing every `HomeRail` needs; everything below turns it into words a
 * writer would actually use, and nothing in this file's public surface ever
 * hands a raw key back to a component to render as a heading.
 *
 * `navLabels` is this site's REAL, currently governed nav — `Map<href
 * without its leading slash, label>`, built by the caller from
 * `getSiteConfig().nav` (`lib/site.ts`) so a department band reads "Resto &
 * Bars section" the day someone renames Dining in the console, not the word
 * "dining" forever. Falls back to a plain, capitalised section name only
 * when this site's nav has no matching item.
 */
export function bandLabel(key: string, navLabels: Map<string, string>): string {
  if (key.startsWith('department:')) {
    const section = key.slice('department:'.length)
    const navLabel = navLabels.get(section)
    return `${navLabel ?? titleCase(section)} section`
  }
  switch (key) {
    case 'lead':
      return 'The cover'
    case 'edit':
      return 'The Edit'
    case 'for-you':
      return 'For you'
    case 'guides':
      return 'Guides'
    case 'latest':
      return 'Latest'
    case 'explore':
      return 'Explore by area'
    default:
      // An unrecognised key (hand-written via the "custom" option, or set by
      // something other than this screen) still never renders as itself —
      // dashes/colons become spaces and the words are capitalised, which
      // reads as an approximation rather than a raw identifier.
      return titleCase(key.replace(/[-:]/g, ' '))
  }
}

function titleCase(s: string): string {
  return s.replace(/\b\w/g, (c) => c.toUpperCase())
}

/**
 * One line, plain words, for the collapsed row — "what fills this if you
 * pin nothing". A description, not a query: the real content is fetched on
 * demand only when a writer expands the band (`refreshAutoFillPreview`),
 * so twelve bands do not mean twelve queries before anyone has looked at
 * any of them.
 */
export function bandFillDescription(key: string, navLabels: Map<string, string>): string {
  if (key.startsWith('department:')) {
    const section = key.slice('department:'.length)
    const navLabel = navLabels.get(section) ?? titleCase(section)
    return `newest ${navLabel} stories`
  }
  switch (key) {
    case 'guides':
      return 'newest guides'
    case 'for-you':
      return 'each reader’s own recommendations — this band is personal, not editable here'
    case 'explore':
      return 'the areas index — not a list of stories'
    default:
      return 'newest stories'
  }
}

/**
 * Bands whose slots a writer may fill by hand. `for-you` is personal to
 * each reader (pinning one story would override that for everyone) and
 * `explore` lists areas, not stories — both are ordered like any other
 * band, and neither is ever searched, pinned or previewed as a story list.
 */
export function bandPinnable(key: string): boolean {
  return key !== 'for-you' && key !== 'explore'
}

/** The catalogue offered when adding a band — human label first, so nothing
 * on this list ever shows a writer a raw key. `custom` is the escape hatch
 * for a key this build does not know about; choosing it reveals a plain
 * text input, clearly marked as advanced, rather than making free-text key
 * entry the default way to add a band. */
export function addableBandTypes(navLabels: Map<string, string>): Array<{ key: string; label: string }> {
  return [
    { key: 'lead', label: bandLabel('lead', navLabels) },
    { key: 'edit', label: bandLabel('edit', navLabels) },
    { key: 'for-you', label: bandLabel('for-you', navLabels) },
    ...DEPARTMENT_SECTIONS.map((s) => ({ key: `department:${s}`, label: bandLabel(`department:${s}`, navLabels) })),
    { key: 'guides', label: bandLabel('guides', navLabels) },
    { key: 'latest', label: bandLabel('latest', navLabels) },
    { key: 'explore', label: bandLabel('explore', navLabels) },
  ]
}
