import { currentReader } from '@/lib/reader'

/**
 * Loads the behavioural beacon (E8.5).
 *
 * The beacon shipped in E0.4, was end-to-end verified, and then **nothing ever
 * loaded it** — it sat in `packages/beacon` while the site collected nothing.
 * ARCHITECTURE §19 is blunt about the cost: *"behavioural data cannot be
 * backfilled. Every week without it delays Stage 2 by a week."*
 *
 * ## Why a plain <script> and not next/script
 *
 * The beacon reads its own `<script>` tag — `document.currentScript` — for
 * both its `data-*` configuration and, from `src`, the origin it posts to.
 * `next/script` with `afterInteractive` injects the tag from a loader, at
 * which point `document.currentScript` is null and the beacon falls back to
 * an empty origin. A plain tag is not a shortcut here, it is the contract.
 *
 * ## Why the endpoint is derived rather than configured
 *
 * The beacon defaults to `<script origin>/v1/{site}/events`, and the engine
 * API is path-routed on the city hostname (ADMIN-CONSOLIDATION.md) — so
 * serving the script from this origin resolves to the right endpoint without
 * a per-city environment variable that could be wrong. `NEXT_PUBLIC_BEACON_ENDPOINT`
 * overrides it for the case where that stops being true.
 *
 * ## Identity
 *
 * `data-user` is rendered server-side from the reader's session, so a signed-in
 * reader's very first event on a page already carries `user_id` — no window
 * where the page has loaded, the reader is signed in, and their behaviour is
 * still landing as anonymous. The beacon filters it through its UUID guard, so
 * a malformed value degrades to anonymous rather than failing the whole batch.
 *
 * ## Entity comes from the page, via <meta>
 *
 * This renders once, in the shared layout, so it cannot know which article is
 * being read. Pages that represent an entity emit `<EntityBeacon>` below; the
 * beacon reads those meta tags at init. One tag site-wide beats a per-page tag
 * that every new route can forget to add.
 */
export async function Beacon({
  site,
  entity,
  entityType = 'article',
  surface = 'site',
}: {
  site: string
  entity?: string
  entityType?: string
  surface?: string
}) {
  if (process.env.BEACON_ENABLED === 'false') return null

  // Failing closed: a reader lookup that throws must not take the page with
  // it. Losing one event is recoverable; a 500 on every article is not.
  let userId: string | undefined
  try {
    userId = (await currentReader())?.id
  } catch {
    userId = undefined
  }

  return (
    <script
      src="/beacon.min.js"
      async
      data-site={site}
      data-entity={entity}
      data-entity-type={entity ? entityType : undefined}
      data-surface={surface}
      data-user={userId}
      data-endpoint={process.env.NEXT_PUBLIC_BEACON_ENDPOINT || undefined}
    />
  )
}

/**
 * What a page renders to say "this page IS this thing".
 *
 * Meta rather than a second script tag: the beacon guards against
 * double-inclusion, so a second tag would be a silent no-op, and the execution
 * order of two async scripts is not guaranteed anyway. These are plain
 * elements in the server-rendered HTML, so they are in the DOM before the
 * async beacon runs.
 */
export function EntityBeacon({
  entity,
  entityType = 'article',
  surface = 'article',
}: {
  entity: string
  entityType?: string
  surface?: string
}) {
  if (!entity) return null
  return (
    <>
      <meta name="nowb:entity" content={entity} />
      <meta name="nowb:entity-type" content={entityType} />
      <meta name="nowb:surface" content={surface} />
    </>
  )
}
