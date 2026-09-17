import 'server-only'

import { headers as nextHeaders } from 'next/headers'
import { redirect } from 'next/navigation'

import { payloadClient } from '@/lib/payload'

/**
 * Who is signed in, and what they may see.
 *
 * Deliberately NOT a copy of the console's version. That one authenticated
 * against a Payload instance bound to `now_platform`, because the console
 * owned that database. Here Payload is bound to the **city** database and
 * identity comes from the platform through the custom strategy
 * (`packages/cms/src/auth/platformStrategy.ts`, Phase 1) — so the session is
 * resolved the same way for editorial and commerce, which is the entire point
 * of the merge.
 *
 * The roles are two independent dimensions (docs/ADMIN-CONSOLIDATION.md):
 * `role` carries editorial standing and `commerceRole` carries commercial.
 * Being an admin of Jakarta's CMS is not a reason to see partner terms.
 */

export type StaffUser = {
  id: number
  email: string
  /** Editorial dimension: admin | editor | author | none */
  role?: string
  /** Commercial dimension: admin | partner_manager | viewer | none */
  commerceRole?: string
}

export async function currentUser(): Promise<StaffUser | null> {
  const payload = await payloadClient()
  const { user } = await payload.auth({ headers: await nextHeaders() })
  return (user as StaffUser | null) ?? null
}

/**
 * For pages that require any signed-in staff member.
 *
 * Redirects to Payload's own login rather than maintaining a second one.
 */
export async function requireUser(): Promise<StaffUser> {
  const user = await currentUser()
  if (!user) redirect('/team-editor/login')
  return user
}

/** May this user see commercial data at all? */
export function canReadCommerce(user: StaffUser): boolean {
  return Boolean(user.commerceRole) && user.commerceRole !== 'none'
}

/** May this user change partnership state? Reserved for the E4.4 write surface. */
export function canManagePartners(user: StaffUser): boolean {
  return user.commerceRole === 'admin' || user.commerceRole === 'partner_manager'
}

/** May this user see editorial content at all? */
export function canReadEditorial(user: StaffUser): boolean {
  return Boolean(user.role) && user.role !== 'none'
}

/**
 * The gate for editorial surfaces that any writer may see.
 *
 * The editorial mirror of `requireCommerceAccess`, and for the same reasons:
 * per route rather than in a layout, because a layout guard is a rendering
 * convenience and not an access control; and a redirect rather than a 403,
 * because a commerce-only user is legitimately signed in and simply has no
 * route here.
 */
export async function requireEditorialAccess(): Promise<StaffUser> {
  const user = await requireUser()
  if (!canReadEditorial(user)) redirect('/team-editor')
  return user
}

/**
 * May this user adjudicate the classifier — accept, correct, or reject what
 * the engine decided about an article?
 *
 * Editor or admin. Deliberately NOT "any editorial user", which is what this
 * surface shipped with. Reviewing is a different job from writing, not a
 * stricter grade of it: the queue is the record of where the engine is wrong,
 * and a decision here is stored with `source='editor'`, which the engine then
 * treats as settled — §8.A's competitor exclusion spends it on a commercial
 * guarantee. A writer correcting their own article's type is editing; a
 * writer deciding 1,726 articles' worth of `type` is setting the taxonomy.
 *
 * Kept in step with `isReviewer` in `packages/cms/src/access` by saying the
 * same thing rather than by importing it: this runs against a `StaffUser`
 * from `payload.auth`, that one against a Payload `req`. If they ever
 * disagree the collection wins, because it is the one the write goes through.
 */
export function canReviewClassification(user: StaffUser): boolean {
  return user.role === 'admin' || user.role === 'editor'
}

/**
 * The gate every classification-review page calls first.
 *
 * Matches `classification-reviews`' own `access` exactly. Gating the page
 * differently from the write it wraps would mean two answers to one question;
 * the one that counts is Payload's, since every write below goes through the
 * Local API with `overrideAccess: false` and this user attached.
 *
 * Redirects to `/team-editor` rather than 403ing. A writer here is not an
 * intruder — they are signed in and doing their job, and this simply is not
 * part of it.
 */
export async function requireReviewerAccess(): Promise<StaffUser> {
  const user = await requireUser()
  if (!canReviewClassification(user)) redirect('/team-editor')
  return user
}

/**
 * The same gate, but returning the user document Payload itself produced
 * rather than this file's `StaffUser` view of it.
 *
 * `StaffUser` is a hand-written shape for rendering — four fields this app
 * cares about. Payload's Local API wants the real document: it hands whatever
 * it is given to every `access` function and every hook as `req.user`, and
 * `reviewQueueHooks.autoPopulateOnDecision` reads `req.user.id` off it to
 * stamp `reviewedBy`. Passing the trimmed shape would work by coincidence
 * today and stop working the moment an access rule reads a field this type
 * never declared. So a write path asks for this and a render path asks for
 * `requireReviewerAccess` — one `payload.auth` either way.
 *
 * Reviewer-gated, like the pages. A server action is not "inside" the page
 * that rendered its form — it compiles to its own POST endpoint with a stable
 * id, reachable by anyone who has ever loaded that page. The page guard
 * protects the reading; this protects the deciding.
 */
export async function requireReviewerActor() {
  const payload = await payloadClient()
  const { user } = await payload.auth({ headers: await nextHeaders() })
  if (!user) redirect('/team-editor/login')
  if (!canReviewClassification(user as StaffUser)) redirect('/team-editor')
  return user
}

/**
 * The gate every commerce page calls first.
 *
 * Enforced server-side, per route — not in a layout. A layout guard is a
 * rendering convenience, not an access control: Next can render a page's data
 * fetch without its parent layout in several situations, and a reader with a
 * direct URL should never be relying on layout order for whether they see
 * partner terms.
 *
 * `notFound`-style behaviour is deliberate for an editorial-only user: they
 * are legitimately signed in, and a 403 would confirm the commerce surface
 * exists. They simply have no route here.
 */
export async function requireCommerceAccess(): Promise<StaffUser> {
  const user = await requireUser()
  if (!canReadCommerce(user)) redirect('/team-editor')
  return user
}

/** May this user create staff accounts and change other people's roles? */
export function canManageStaff(user: StaffUser): boolean {
  return user.role === 'admin'
}

/**
 * The gate the staff surface calls first — in every page AND every action.
 *
 * **The editorial dimension, not the commercial one.** Commerce `admin` is
 * admin *of partner data*; granting it the power to mint editorial accounts
 * would make the two dimensions one again, which is the thing
 * docs/ADMIN-CONSOLIDATION.md separated them to avoid. A partner manager who
 * needs to onboard someone asks an editorial admin.
 *
 * Per route and per action, for the reason spelled out on
 * `requireCommerceAccess` above — with one thing added that matters more
 * here. A server action is not "inside" the page that rendered its form: it
 * compiles to its own POST endpoint with its own stable id, reachable by
 * anyone who has ever seen the page's payload. A guard on the page protects
 * the table; it does nothing at all for the action that grants roles. Hence
 * `requireStaffAdmin()` as the first line of every export in
 * `team-editor/staff/actions.ts`, not once in a layout.
 */
export async function requireStaffAdmin(): Promise<StaffUser> {
  const user = await requireUser()
  if (!canManageStaff(user)) redirect('/team-editor')
  return user
}
