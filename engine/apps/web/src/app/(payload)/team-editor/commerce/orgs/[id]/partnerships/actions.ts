'use server'

import { revalidatePath } from 'next/cache'

import { canWritePartnershipForSite, commerceCurrentSiteSlug, requireCommerceWriter } from '@/lib/auth'
import {
  computeBlastRadius,
  createPartnership,
  getPartnership,
  updatePartnership,
  type BlastRadius,
  type NewPartnershipInput,
  type PartnershipDetail,
  type PartnershipStatus,
  type PartnershipTier,
} from '@/lib/queries'

import { orgHref, partnershipHref } from '../../../paths'

/**
 * The write half of S5.2 — the whole reason `engine.partnerships` stops
 * being an empty table.
 *
 * **Two gates, checked in order, for two different failures.** First
 * `requireCommerceWriter()` (`lib/auth.ts`): no session, or a commerce role
 * that cannot write at all (`viewer`, `none`, or an editorial-only `author`
 * with no commerce role) — redirected off the surface entirely, the same
 * hard stop `requireStaffAdmin` uses for staff management. Second,
 * `canWritePartnershipForSite`: a real writer (`admin` or `partner_manager`)
 * naming a site this process is not allowed to write on their behalf —
 * answered as an ordinary form error, not a redirect, because picking the
 * wrong site in a dropdown is not an intrusion attempt. See `lib/auth.ts`'s
 * comments on both for the full argument.
 *
 * **The blast radius is computed twice, by design, and both times for real.**
 * `previewSave` runs it before anything is written, so the confirmation
 * screen and the actual commit can never disagree about what "this affects
 * N articles" meant at save time — there is no second, faster approximation
 * anywhere in this file.
 */

export type PartnershipFormValues = {
  orgId: string | null
  placeId: string | null
  siteSlug: string
  siteId: string
  tier: PartnershipTier
  status: PartnershipStatus
  startsAt: string
  endsAt: string
  linkPolicyJson: string
  customUrl: string
  utmTemplate: string
  showBadge: boolean
  badgeLabel: string
  itineraryEligible: boolean
  boostCap: string
}

export type PartnershipActionResult =
  | { ok: true; message: string; partnership: PartnershipDetail }
  | { ok: false; message: string }

export type PreviewResult =
  | { ok: true; blastRadius: BlastRadius }
  | { ok: false; message: string }

function parseLinkPolicy(raw: string): { value: Record<string, unknown> } | { error: string } {
  const trimmed = raw.trim()
  if (trimmed === '') return { value: {} }
  try {
    const parsed = JSON.parse(trimmed)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      return { error: 'Link policy must be a JSON object, e.g. {} or {"noindex": true}.' }
    }
    return { value: parsed as Record<string, unknown> }
  } catch {
    return { error: 'Link policy is not valid JSON. Leave it blank for the default, {}.' }
  }
}

function parseBoostCap(raw: string): { value: number | null } | { error: string } {
  const trimmed = raw.trim()
  if (trimmed === '') return { value: null }
  const n = Number(trimmed)
  if (!Number.isFinite(n) || n < 0 || n > 1) {
    return { error: 'Boost cap must be a number between 0 and 1 (a share of a rail, not a percent), or left blank.' }
  }
  return { value: n }
}

function describeFieldProblem(values: PartnershipFormValues): string | null {
  const hasOrg = Boolean(values.orgId)
  const hasPlace = Boolean(values.placeId)
  if (hasOrg === hasPlace) {
    return 'A partnership names exactly one of an organisation or a place — never both, never neither.'
  }
  if (values.tier === 'paid' && !values.customUrl.trim()) {
    return 'A paid partnership needs a custom URL — that is what the in-article link and the badge point at.'
  }
  if (values.startsAt && values.endsAt && values.startsAt > values.endsAt) {
    return 'The contract cannot end before it starts.'
  }
  return null
}

/**
 * Read-only. Validates the form and reports what committing it would touch,
 * without writing anything — the screen `PartnershipForm.tsx` shows before
 * the actual save, and the only door through it (S5.3: "dismissible only by
 * confirming").
 */
export async function previewPartnershipSave(values: PartnershipFormValues): Promise<PreviewResult> {
  const actor = await requireCommerceWriter()
  if (!canWritePartnershipForSite(actor, commerceCurrentSiteSlug(), values.siteSlug)) {
    return {
      ok: false,
      message: `You may only write partnerships for ${commerceCurrentSiteSlug() || 'your own city'}. This one targets ${values.siteSlug}.`,
    }
  }
  const problem = describeFieldProblem(values)
  if (problem) return { ok: false, message: problem }

  const blastRadius = await computeBlastRadius({
    orgId: values.orgId,
    placeId: values.placeId,
    targetSiteSlug: values.siteSlug,
  })
  return { ok: true, blastRadius }
}

export async function createPartnershipAction(values: PartnershipFormValues): Promise<PartnershipActionResult> {
  const actor = await requireCommerceWriter()
  if (!canWritePartnershipForSite(actor, commerceCurrentSiteSlug(), values.siteSlug)) {
    return {
      ok: false,
      message: `You may only write partnerships for ${commerceCurrentSiteSlug() || 'your own city'}. This one targets ${values.siteSlug}.`,
    }
  }
  const problem = describeFieldProblem(values)
  if (problem) return { ok: false, message: problem }

  const linkPolicy = parseLinkPolicy(values.linkPolicyJson)
  if ('error' in linkPolicy) return { ok: false, message: linkPolicy.error }
  const boostCap = parseBoostCap(values.boostCap)
  if ('error' in boostCap) return { ok: false, message: boostCap.error }

  const input: NewPartnershipInput = {
    orgId: values.orgId,
    placeId: values.placeId,
    siteId: values.siteId,
    tier: values.tier,
    status: values.status,
    startsAt: values.startsAt || null,
    endsAt: values.endsAt || null,
    linkPolicy: linkPolicy.value,
    customUrl: values.customUrl.trim() || null,
    utmTemplate: values.utmTemplate.trim() || null,
    showBadge: values.showBadge,
    badgeLabel: values.badgeLabel.trim() || null,
    itineraryEligible: values.itineraryEligible,
    boostCap: boostCap.value,
  }

  const partnership = await createPartnership(input, { id: actor.id, email: actor.email })
  console.info(
    '[commerce] %s created partnership %s (tier=%s, site=%s)',
    actor.email,
    partnership.id,
    partnership.tier,
    partnership.siteSlug,
  )
  if (values.orgId) revalidatePath(orgHref(values.orgId))
  return { ok: true, message: `Created the ${partnership.tier} partnership for ${partnership.siteSlug}.`, partnership }
}

export async function updatePartnershipAction(
  id: string,
  values: PartnershipFormValues,
): Promise<PartnershipActionResult> {
  const actor = await requireCommerceWriter()

  const existing = await getPartnership(id)
  if (!existing) return { ok: false, message: 'That partnership no longer exists.' }

  // The site a row targets is write-once (`createPartnership`'s own
  // comment) — the scope check always uses the ROW's real site, never
  // whatever `values.siteSlug` says, so a tampered form field cannot widen
  // what an edit is allowed to touch.
  if (!canWritePartnershipForSite(actor, commerceCurrentSiteSlug(), existing.siteSlug)) {
    return {
      ok: false,
      message: `You may only write partnerships for ${commerceCurrentSiteSlug() || 'your own city'}. This one targets ${existing.siteSlug}.`,
    }
  }

  const problem = describeFieldProblem({ ...values, siteSlug: existing.siteSlug })
  if (problem) return { ok: false, message: problem }

  const linkPolicy = parseLinkPolicy(values.linkPolicyJson)
  if ('error' in linkPolicy) return { ok: false, message: linkPolicy.error }
  const boostCap = parseBoostCap(values.boostCap)
  if ('error' in boostCap) return { ok: false, message: boostCap.error }

  const scope = actor.commerceRole === 'admin' ? 'any' : commerceCurrentSiteSlug()
  const result = await updatePartnership(
    id,
    {
      tier: values.tier,
      status: values.status,
      startsAt: values.startsAt || null,
      endsAt: values.endsAt || null,
      linkPolicy: linkPolicy.value,
      customUrl: values.customUrl.trim() || null,
      utmTemplate: values.utmTemplate.trim() || null,
      showBadge: values.showBadge,
      badgeLabel: values.badgeLabel.trim() || null,
      itineraryEligible: values.itineraryEligible,
      boostCap: boostCap.value,
    },
    { id: actor.id, email: actor.email },
    scope,
  )

  if (!result.ok) {
    return { ok: false, message: 'That partnership could not be updated — it may no longer exist, or belong to a site you cannot write.' }
  }

  console.info('[commerce] %s updated partnership %s', actor.email, id)
  if (result.partnership.orgId) revalidatePath(orgHref(result.partnership.orgId))
  revalidatePath(partnershipHref(result.partnership.orgId ?? '', id))
  return { ok: true, message: `Saved the ${result.partnership.tier} partnership for ${result.partnership.siteSlug}.`, partnership: result.partnership }
}
