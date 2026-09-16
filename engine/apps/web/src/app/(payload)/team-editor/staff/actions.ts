'use server'

import crypto from 'node:crypto'

import { hashPassword, isCommerceRole, isEditorialRole, normaliseEmail } from '@now/auth'
import type { CommerceRole, EditorialRole } from '@now/auth'
import { revalidatePath } from 'next/cache'

import { requireStaffAdmin } from '@/lib/auth'
import {
  clearStaffLockout,
  createStaffAccount,
  findStaff,
  resetStaffCredential,
  updateStaffRoles,
} from '@/lib/staff'

import { STAFF_ROOT } from './paths'

/**
 * The write half of the staff surface.
 *
 * Until this existed the only way to create an account or change a role was
 * `npm run staff-account -w @now/auth` on a shell with
 * `PLATFORM_DATABASE_URI` in the environment — which meant nobody could be
 * onboarded to the CMS without the one person who has that shell. The script
 * stays: it is how the *first* admin is minted, and there is no chicken-egg
 * escape from that. Everything after the first admin happens here.
 *
 * These call `hashPassword` from `@now/auth` rather than reaching for
 * `crypto.pbkdf2` directly. The parameters there are *matched* to Payload
 * 3.88.0, not chosen (see `packages/auth/src/password.ts`); a second
 * implementation is a second set of constants that can drift, and the way
 * that drift shows up is a credential this surface mints and the sign-in
 * route then rejects.
 *
 * ## Two rules that are not negotiable
 *
 * 1. **`requireStaffAdmin()` is the first line of every export.** A server
 *    action is its own POST endpoint, not a part of the page that rendered
 *    the form (see lib/auth.ts).
 * 2. **A generated password is returned to the caller and written nowhere
 *    else.** Not to a redirect query string — that lands in browser history,
 *    the server access log and any `Referer` the next request sends — not to
 *    a cookie, not to a log line. It exists in the action's reply and in the
 *    React state of the component that renders it, and is gone on reload.
 */

export type StaffActionResult = {
  ok: boolean
  message: string
  /**
   * Set only by the two actions that mint a password, and only in the reply
   * to the call that minted it. There is no second way to read it back.
   */
  credential?: { email: string; password: string }
}

/**
 * 18 random bytes, base64url — the same generator as
 * `scripts/staff-account.mjs`, deliberately. Long enough that the
 * 25k-iteration PBKDF2 behind it never has to carry the weight, and
 * unambiguous to read aloud or paste.
 */
function generatePassword(): string {
  return crypto.randomBytes(18).toString('base64url')
}

/**
 * Good enough to catch a typo, and nothing more.
 *
 * Deliberately not an RFC 5322 attempt: the addresses here are colleagues'
 * work addresses typed by an admin who can see the result, and an
 * over-strict pattern that rejects a real address is a worse failure than a
 * loose one that lets a wrong-but-plausible address through.
 */
function looksLikeEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}

function field(form: FormData, name: string): string {
  const value = form.get(name)
  return typeof value === 'string' ? value.trim() : ''
}

/** Roles arrive as strings from a `<select>`; a POST can carry anything. */
function readRoles(
  editorial: unknown,
  commerce: unknown,
): { editorial: EditorialRole; commerce: CommerceRole } | null {
  if (!isEditorialRole(editorial) || !isCommerceRole(commerce)) return null
  return { editorial, commerce }
}

export async function inviteStaff(form: FormData): Promise<StaffActionResult> {
  const actor = await requireStaffAdmin()

  const email = normaliseEmail(field(form, 'email'))
  const name = field(form, 'name')
  const roles = readRoles(form.get('editorialRole'), form.get('commerceRole'))

  if (!email || !looksLikeEmail(email)) {
    return { ok: false, message: 'Enter a valid email address.' }
  }
  if (!roles) {
    return { ok: false, message: 'Pick a role on each dimension.' }
  }
  // Both `none` is a real database state — a row that exists for audit
  // history — but it is never what someone pressing "Invite" meant, and
  // `hasAnyAccess` would refuse the sign-in anyway. Failing here says so
  // once instead of at their first attempt to log in.
  if (roles.editorial === 'none' && roles.commerce === 'none') {
    return {
      ok: false,
      message: 'Both roles are “none”, so this account could sign in and see nothing.',
    }
  }

  const password = generatePassword()
  const { hash, salt } = await hashPassword(password)

  const created = await createStaffAccount({
    email,
    name: name || null,
    editorialRole: roles.editorial,
    commerceRole: roles.commerce,
    hash,
    salt,
  })

  if (!created) {
    return {
      ok: false,
      message: `${email} already has an account. Change their roles or reset their password below.`,
    }
  }

  console.info('[staff] %s created account %s', actor.email, email)
  revalidatePath(STAFF_ROOT)
  return {
    ok: true,
    message: `Created ${email}. This password is shown once.`,
    credential: { email, password },
  }
}

export async function changeRoles(
  id: number,
  editorialRole: string,
  commerceRole: string,
): Promise<StaffActionResult> {
  const actor = await requireStaffAdmin()

  const roles = readRoles(editorialRole, commerceRole)
  if (!roles) return { ok: false, message: 'That is not a role this build recognises.' }

  const target = await findStaff(id)
  if (!target) return { ok: false, message: 'That account no longer exists.' }

  /**
   * **Nobody may take their own admin role away.**
   *
   * This is the one move that can leave an organisation with no way back in:
   * losing `admin` loses this surface, and the only remedy is a shell on the
   * box with `PLATFORM_DATABASE_URI` set. Compared by email rather than id
   * because the id on the session is the *city shadow* row's, which is a
   * different sequence in a different database to the platform id these rows
   * carry — comparing those two would compare unrelated numbers and
   * occasionally match.
   *
   * There is no separate "last admin" guard, and none is needed: an admin can
   * only demote someone who is not themselves, so at least the actor always
   * remains. The zero-admin state is unreachable once this check holds.
   */
  if (normaliseEmail(target.email) === normaliseEmail(actor.email) && roles.editorial !== 'admin') {
    return {
      ok: false,
      message: 'You cannot remove your own administrator role. Ask another admin to do it.',
    }
  }

  const updated = await updateStaffRoles(id, roles.editorial, roles.commerce)
  if (!updated) return { ok: false, message: 'That account no longer exists.' }

  console.info(
    '[staff] %s set %s to editorial=%s commerce=%s',
    actor.email,
    updated.email,
    updated.editorialRole,
    updated.commerceRole,
  )
  revalidatePath(STAFF_ROOT)
  return { ok: true, message: `Saved roles for ${updated.email}.` }
}

export async function resetPassword(id: number): Promise<StaffActionResult> {
  const actor = await requireStaffAdmin()

  const target = await findStaff(id)
  if (!target) return { ok: false, message: 'That account no longer exists.' }

  const password = generatePassword()
  const { hash, salt } = await hashPassword(password)

  const updated = await resetStaffCredential(id, hash, salt)
  if (!updated) return { ok: false, message: 'That account no longer exists.' }

  console.info('[staff] %s reset the password for %s', actor.email, updated.email)
  revalidatePath(STAFF_ROOT)
  return {
    ok: true,
    message: `New password for ${updated.email}. Shown once.`,
    credential: { email: updated.email, password },
  }
}

/**
 * Unlock without issuing a new password.
 *
 * Separate from the reset above because the common case is someone who
 * mistyped their password eight times and still knows it. Handing them a new
 * one to solve that is a worse outcome than clearing the counter.
 */
export async function unlockAccount(id: number): Promise<StaffActionResult> {
  const actor = await requireStaffAdmin()

  const updated = await clearStaffLockout(id)
  if (!updated) return { ok: false, message: 'That account no longer exists.' }

  console.info('[staff] %s cleared the lockout on %s', actor.email, updated.email)
  revalidatePath(STAFF_ROOT)
  return { ok: true, message: `Cleared the lockout on ${updated.email}.` }
}
