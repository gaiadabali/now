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

export const NON_DEPARTMENT_BAND_KEYS = ['lead', 'edit', 'for-you', 'guides', 'latest', 'explore'] as const

/** A sensible starting order for a site whose `home_rails` has never been
 * saved — not a claim about what the home page currently renders, which
 * WS2 owns, only a scaffold so an editor has bands to arrange rather than a
 * blank screen and seven key names to remember. */
export function defaultBandOrder(): string[] {
  return [
    'lead',
    'edit',
    'for-you',
    ...DEPARTMENT_SECTIONS.map((s) => `department:${s}`),
    'guides',
    'latest',
    'explore',
  ]
}

/** Bands that are a list of stories — the only ones pinning applies to.
 * `explore` is the areas index (DESIGN-SYSTEM.md §3), not stories. */
export function bandHoldsStories(key: string): boolean {
  return key !== 'explore'
}

export function bandLabel(key: string): string {
  if (key.startsWith('department:')) {
    const section = key.slice('department:'.length)
    return `Department — ${section.replace(/-/g, ' ')}`
  }
  switch (key) {
    case 'lead':
      return 'Lead (the cover)'
    case 'edit':
      return 'The Edit'
    case 'for-you':
      return 'For you'
    case 'guides':
      return 'Guides'
    case 'latest':
      return 'Latest'
    case 'explore':
      return 'Explore (areas)'
    default:
      return key
  }
}
