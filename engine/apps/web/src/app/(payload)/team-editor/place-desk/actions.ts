'use server'

import { revalidatePath } from 'next/cache'
import { commitTransaction, createLocalReq, initTransaction, killTransaction } from 'payload'

import { requireReviewerActor } from '@/lib/auth'
import { payloadClient } from '@/lib/payload'
import { areaOptions, deskPlace, stillJunkCandidates, subtypeOptions } from '@/lib/placeDesk'
import { approvalCheck, mergeEntry } from '@/lib/placeDeskRules'
import { getSiteConfig } from '@/lib/site'

import { BULK_JUNK_BATCH, DESK_ROOT, placeHref } from './paths'

/**
 * Every place-desk decision, as a Payload write.
 *
 * Plan P1.6: "every decision is a Payload version with the actor". So no
 * raw SQL here: each write is `payload.update` with the signed-in reviewer
 * attached and `overrideAccess: false`, which runs the `places` hooks
 * (`placeReviewGate`: editor/admin only for approve, junk and merge; stamps
 * `reviewedBy` and `verifiedAt`) and records a version.
 *
 * `requireReviewerActor()` is the first line of every action: a server
 * action compiles to its own POST endpoint, so the page's guard does not
 * protect it. Ids come from the form, but what may be done to them is
 * re-derived here (the place's current state, the junk verdict), never
 * trusted from the page that rendered the button.
 */

export type DeskResult = { ok: true; message: string } | { ok: false; error: string }

type Actor = { id: number | string; email?: string }

const actorLabel = (user: Actor) => `desk:${user.id}${user.email ? ` ${user.email}` : ''}`

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

const DECISIONS = new Set(['keep', 'junk', 'approve', 'reopen', 'type', 'area'])

export async function decide(_previous: DeskResult | null, form: FormData): Promise<DeskResult> {
  const user = (await requireReviewerActor()) as unknown as Actor
  const id = Number(form.get('id'))
  const decision = String(form.get('decision') ?? '')
  if (!Number.isInteger(id)) return { ok: false, error: 'No place was named.' }
  if (!DECISIONS.has(decision)) return { ok: false, error: `"${decision}" is not a desk decision.` }

  const place = await deskPlace(id)
  if (!place) return { ok: false, error: 'That place no longer exists.' }
  if (place.mergedInto) {
    return { ok: false, error: `This place was merged into "${place.mergedIntoName ?? place.mergedInto}". Decide that one instead.` }
  }

  let data: Record<string, unknown>
  let message: string
  switch (decision) {
    case 'keep':
      if (place.status !== 'pending_review') return { ok: false, error: 'Only a place still waiting can be kept.' }
      data = { reviewedBy: user.id }
      message = 'Kept. It stays in the queue as a real place, off the junk list.'
      break
    case 'junk':
      if (place.status === 'junk') return { ok: false, error: 'Already marked as junk.' }
      if (place.status === 'active') return { ok: false, error: 'This place is live. Put it back in the queue before marking it as junk.' }
      data = { status: 'junk', reviewedBy: user.id }
      message = 'Marked as junk. It is hidden everywhere; its mentions are kept.'
      break
    case 'approve': {
      const check = approvalCheck(place)
      if (!check.ok) return { ok: false, error: check.why }
      data = { status: 'active', reviewedBy: user.id, verifiedAt: new Date().toISOString() }
      message = 'Approved. Its page is live.'
      break
    }
    case 'reopen':
      if (place.status === 'pending_review') return { ok: false, error: 'It is already in the queue.' }
      data = { status: 'pending_review', reviewedBy: user.id }
      message = place.status === 'active' ? 'Taken down and put back in the queue.' : 'Put back in the queue.'
      break
    case 'type': {
      const subtype = String(form.get('subtype') ?? '')
      const group = (await subtypeOptions()).find((g) => g.subtypes.some((s) => s.slug === subtype))
      if (!group) return { ok: false, error: 'Choose what kind of place it is from the list.' }
      data = { type: group.type, subtype, reviewedBy: user.id }
      message = `Set to ${group.subtypes.find((s) => s.slug === subtype)?.label ?? subtype} (${group.label}).`
      break
    }
    case 'area': {
      const area = String(form.get('area') ?? '')
      const site = await getSiteConfig()
      const { home, elsewhere } = await areaOptions(site.slug)
      const option = [...home, ...elsewhere].find((a) => a.slug === area)
      if (!option) return { ok: false, error: 'Choose an area from the list.' }
      data = { areaTerm: area, reviewedBy: user.id }
      message = `Area set to ${option.label}.`
      break
    }
    default:
      return { ok: false, error: 'Unknown decision.' }
  }

  try {
    const payload = await payloadClient()
    await payload.update({ collection: 'places', id, data, user: user as never, overrideAccess: false, depth: 0 })
  } catch (err) {
    // Verbatim: the gate and Payload's validation both say what to do next.
    return { ok: false, error: errorText(err) }
  }
  revalidatePath(DESK_ROOT)
  revalidatePath(placeHref(id))
  revalidatePath(`/places/${place.slug}`)
  return { ok: true, message }
}

/**
 * Merge one place into another, as ONE transaction of Payload writes: the
 * loser's mentions move to the survivor, anything previously merged into
 * the loser is re-pointed, `mergedInto` is set, and the survivor's
 * `aliases` gains the audit entry (`placeDeskRules.mergeEntry`, the shape
 * `now-places merge` writes). If any step fails, nothing is kept.
 */
export async function merge(_previous: DeskResult | null, form: FormData): Promise<DeskResult> {
  const user = (await requireReviewerActor()) as unknown as Actor
  const id = Number(form.get('id'))
  const other = Number(form.get('other'))
  const direction = String(form.get('direction') ?? '')
  if (!Number.isInteger(id) || !Number.isInteger(other) || id === other) {
    return { ok: false, error: 'Choose two different places.' }
  }
  if (direction !== 'into-this' && direction !== 'into-other') return { ok: false, error: 'Say which place survives.' }
  const [loserId, survivorId] = direction === 'into-this' ? [other, id] : [id, other]

  const [loser, survivor] = await Promise.all([deskPlace(loserId), deskPlace(survivorId)])
  if (!loser || !survivor) return { ok: false, error: 'One of those places no longer exists.' }
  if (loser.mergedInto || survivor.mergedInto) return { ok: false, error: 'One of those places has already been merged.' }
  if (loser.status === 'active') {
    return { ok: false, error: `"${loser.name}" is live. Put it back in the queue first, or merge the other way round.` }
  }

  const payload = await payloadClient()
  const req = await createLocalReq({ user: user as never }, payload)
  await initTransaction(req)
  try {
    const common = { req, user: user as never, overrideAccess: false, depth: 0 } as const
    const mentions = await payload.find({
      collection: 'place-mentions',
      where: { place: { equals: loserId } },
      pagination: false,
      ...common,
    })
    const mentionIds = mentions.docs.map((d) => Number(d.id))
    for (const mid of mentionIds) {
      await payload.update({ collection: 'place-mentions', id: mid, data: { place: survivorId }, ...common })
    }
    const earlier = await payload.find({
      collection: 'places',
      where: { mergedInto: { equals: loserId } },
      pagination: false,
      ...common,
    })
    const repointed = earlier.docs.map((d) => Number(d.id))
    for (const pid of repointed) {
      await payload.update({ collection: 'places', id: pid, data: { mergedInto: survivorId, reviewedBy: user.id }, ...common })
    }
    await payload.update({ collection: 'places', id: loserId, data: { mergedInto: survivorId, reviewedBy: user.id }, ...common })
    const entry = mergeEntry({
      loser: { id: loserId, name: loser.name, aliases: loser.aliases },
      mentionIds,
      repointedPlaceIds: repointed,
      by: actorLabel(user),
      at: new Date(),
    })
    const aliases = Array.isArray(survivor.aliases) ? [...survivor.aliases, entry] : [entry]
    await payload.update({ collection: 'places', id: survivorId, data: { aliases, reviewedBy: user.id }, ...common })
    await commitTransaction(req)
    revalidatePath(DESK_ROOT)
    revalidatePath(placeHref(loserId))
    revalidatePath(placeHref(survivorId))
    return {
      ok: true,
      message: `Merged "${loser.name}" into "${survivor.name}": ${mentionIds.length} mention${mentionIds.length === 1 ? '' : 's'} moved, both names kept.`,
    }
  } catch (err) {
    await killTransaction(req)
    return { ok: false, error: `Nothing was changed. ${errorText(err)}` }
  }
}

/** Four writes at a time: each runs the place hooks and records a version on
 * the same pool the page reads from (the classification desk's reasoning). */
const CONCURRENCY = 4

export async function bulkJunk(_previous: DeskResult | null, form: FormData): Promise<DeskResult> {
  const user = (await requireReviewerActor()) as unknown as Actor
  const asked = form
    .getAll('ids')
    .map((v) => Number(v))
    .filter((n) => Number.isInteger(n))
    .slice(0, BULK_JUNK_BATCH)
  if (!asked.length) return { ok: false, error: 'Tick at least one place.' }

  // Only rows that are STILL pending, unkept and junk-shaped: a colleague
  // may have kept or decided some since the page loaded.
  const ids = await stillJunkCandidates(asked)
  if (!ids.length) return { ok: true, message: 'Nothing left to mark: those have all been decided.' }

  const payload = await payloadClient()
  let done = 0
  let failed = 0
  let firstError: string | null = null
  const queue = [...ids]
  await Promise.all(
    Array.from({ length: Math.min(CONCURRENCY, queue.length) }, async () => {
      for (let id = queue.shift(); id !== undefined; id = queue.shift()) {
        try {
          await payload.update({
            collection: 'places',
            id,
            data: { status: 'junk', reviewedBy: user.id },
            user: user as never,
            overrideAccess: false,
            depth: 0,
          })
          done += 1
        } catch (err) {
          failed += 1
          firstError ??= errorText(err)
        }
      }
    }),
  )
  revalidatePath(DESK_ROOT)
  if (!done) return { ok: false, error: firstError ?? 'Nothing was marked, and nothing said why.' }
  const skipped = asked.length - ids.length
  return {
    ok: true,
    message:
      `${done} marked as junk.` +
      (skipped ? ` ${skipped} skipped: someone decided them first.` : '') +
      (failed ? ` ${failed} refused: ${firstError}` : ''),
  }
}
