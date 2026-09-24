'use server'

import { revalidatePath } from 'next/cache'

import { requireCommerceWriter, requireCommerceWriterActor } from '@/lib/auth'
import { payloadClient } from '@/lib/payload'
import { searchCityPlaces } from '@/lib/queries'
import type { CityPlace } from '@/lib/queries'

import { orgHref } from '../../paths'

/**
 * Linking a venue to an organisation — S5.2's second write path, and the
 * one that makes a partnership do anything at all. `engine.partnerships`
 * resolves per organisation (or per place), but a partnership on an
 * organisation with no linked venue has nothing to apply to: the blast
 * radius is real and it is zero, because `places.org_id` is empty on every
 * row in this city.
 *
 * **Payload's Local API, not raw SQL** — `places` is a city collection with
 * its own hooks and version history (`packages/cms/src/collections/
 * Places.ts`), and it already has the field this needs: `orgId`, a plain
 * text column holding the platform-DB org uuid (cross-database, so it
 * cannot be a real Payload relationship — see that file's own comment).
 * Writing it with `payload.update()` means a version is recorded the way
 * every other places edit is, and any future hook on this collection sees
 * the write; a second SQL path around Payload would see neither.
 *
 * **Gated the same way partnership writes are** — `requireCommerceWriter()`
 * (`canManagePartners`: commerce `admin` or `partner_manager`), not
 * `places`' own `isAuthorOrAbove` access (the EDITORIAL dimension, judged on
 * a different role entirely — see `requireCommerceWriterActor`'s comment).
 * No site-scope check the way partnership writes get one: this process
 * only ever has ONE city's places to search or attach in the first place
 * (`cityPool()`/Payload are both bound to `DATABASE_URI`), so there is no
 * "wrong site" a venue link could target.
 */

export type VenueActionResult = { ok: boolean; message: string }

export async function searchVenues(term: string): Promise<CityPlace[]> {
  // Read-gated at the same level as the write it exists to feed — this is
  // the picker for attaching a venue, not a general places browser.
  await requireCommerceWriter()
  return searchCityPlaces(term)
}

export async function attachVenue(orgId: string, placeId: string): Promise<VenueActionResult> {
  const actor = await requireCommerceWriter()
  const user = await requireCommerceWriterActor()
  const payload = await payloadClient()

  try {
    const place = await payload.update({
      collection: 'places',
      id: placeId,
      data: { orgId },
      user,
      overrideAccess: true,
      depth: 0,
    })
    const name = (place as { name?: string }).name ?? 'That venue'
    console.info('[commerce] %s linked place %s (%s) to org %s', actor.email, placeId, name, orgId)
    revalidatePath(orgHref(orgId))
    return { ok: true, message: `Linked ${name} to this organisation.` }
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : 'That venue could not be linked.' }
  }
}

export async function detachVenue(orgId: string, placeId: string): Promise<VenueActionResult> {
  const actor = await requireCommerceWriter()
  const user = await requireCommerceWriterActor()
  const payload = await payloadClient()

  try {
    const place = await payload.update({
      collection: 'places',
      id: placeId,
      data: { orgId: null },
      user,
      overrideAccess: true,
      depth: 0,
    })
    const name = (place as { name?: string }).name ?? 'That venue'
    console.info('[commerce] %s unlinked place %s (%s) from org %s', actor.email, placeId, name, orgId)
    revalidatePath(orgHref(orgId))
    return { ok: true, message: `Unlinked ${name} from this organisation.` }
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : 'That venue could not be unlinked.' }
  }
}
