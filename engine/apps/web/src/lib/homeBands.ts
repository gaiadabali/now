import type { HomeRail } from '@/lib/site'

/**
 * The home page's band order when `sites.home_rails` has never been saved —
 * the ONE list, read by the home page (`lib/frontPage.ts`) and by the desk's
 * front-page editor as its starting point.
 *
 * Its own module, with no runtime imports, because the editor is a client
 * component and `lib/frontPage.ts` is `server-only`. Before this, the editor
 * kept its own twelve-band scaffold, so the first time anyone pressed Save
 * the home page turned into six department bands back to back — a layout no
 * one had chosen, produced by a list no reader had ever seen.
 *
 * `for-you` sits right after `edit` so a personal rail appears the day
 * `getForYou` returns one, with no change here — a null rail renders nothing.
 */
export const DEFAULT_HOME_RAILS: readonly HomeRail[] = [
  { key: 'lead' },
  { key: 'edit' },
  { key: 'for-you' },
  { key: 'department:stay' },
  { key: 'guides' },
  { key: 'latest' },
  { key: 'explore' },
]
