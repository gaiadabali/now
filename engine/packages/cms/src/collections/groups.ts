/**
 * The four headings the admin sidebar is grouped under.
 *
 * Until S3.2 there were none. Payload lists collections flat and in config
 * order, so the sidebar read: Articles · Places · Classification reviews ·
 * Events · Place mentions · Media · Authors · Users. Eight items, one list, no
 * indication that a writer needs four of them and will never touch the rest.
 *
 * The grouping is by WHOSE JOB IT IS, not by data model — which is why Events
 * and Media sit with Articles rather than in a "Content" group with Places,
 * and why Place mentions sits away from Places despite the name. A writer
 * opens Editorial. Someone curating venues opens Places. Engine is what the
 * classifier produced and what a reviewer adjudicates. Settings is neither.
 *
 * Order matters and is set by `collections:` in payload.config.ts, since
 * Payload renders groups in the order it first meets them. Editorial is first
 * because it is the daily work.
 *
 * Plain words, not internal vocabulary. "Engine" is the one term of art left
 * and it is the right one — it is what this project calls the thing, it
 * appears in the architecture doc and in the API's own name, and a reviewer
 * adjudicating classifications is working on the engine's output.
 */
export const GROUPS = {
  /** The daily work: what gets written, and what goes in it. */
  editorial: 'Editorial',
  /** Venues, hotels, restaurants — curated continuously, not written once. */
  places: 'Places',
  /** What the classifier decided, and the queue for telling it it was wrong. */
  engine: 'Engine',
  /** Accounts. Mirrored from the platform and read-only here. */
  settings: 'Settings',
} as const
