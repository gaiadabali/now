'use client'

import { useEffect, useRef, useState, useTransition } from 'react'

import type { StaffMember } from '@/lib/staff'

import { changeRoles, inviteStaff, resetPassword, unlockAccount } from './actions'
import type { StaffActionResult } from './actions'
import { COMMERCE_LABELS, COMMERCE_ORDER, EDITORIAL_LABELS, EDITORIAL_ORDER } from './roles'

/**
 * The whole staff surface's interaction, in one client component.
 *
 * **Why one component and not four.** A generated password is rendered in
 * exactly one place — the notice panel below — no matter which action minted
 * it. Splitting invite, reset and unlock into separate islands would give the
 * secret two or three render sites to audit instead of one, and this is the
 * file where that audit happens.
 *
 * **Why client-side at all**, when the account forms in `(site)/account` are
 * deliberately plain `<form action={…}>` posts that work without JavaScript:
 * those are public pages a reader may reach with JS blocked. This one renders
 * inside Payload's admin, which is a React application that does not run at
 * all without JavaScript — there is no no-JS user to serve here, and a
 * redirect-based flow would have to carry the generated password in a query
 * string to show it. That string lands in browser history, the access log and
 * the next request's `Referer`. Holding it in component state instead means
 * it is gone on reload, which is what "shown once" has to mean.
 *
 * Every button goes through a server action that re-checks the caller is an
 * editorial admin. Nothing here is a permission check; the disabled states
 * below are courtesy, not control.
 */

type Props = {
  members: StaffMember[]
  /** The signed-in admin, for the you-cannot-demote-yourself affordance. */
  actorEmail: string
}

const IDLE: StaffActionResult | null = null

export function StaffConsole({ members, actorEmail }: Props) {
  const [notice, setNotice] = useState(IDLE)
  const [pending, startTransition] = useTransition()
  const noticeRef = useRef<HTMLDivElement>(null)

  /**
   * True once React has attached handlers to this tree.
   *
   * The invite form is a `<form>` with an `onSubmit` and no `action`, so
   * until hydration runs the browser's own default applies: pressing the
   * button navigates to the current URL with every field appended as a query
   * string. Caught driving the real page — the click landed during the first
   * compile and produced
   *
   *     GET /team-editor/staff?email=…&editorialRole=editor…
   *
   * which created nothing, said nothing, and put a colleague's address in the
   * address bar and the access log. Payload's admin is a heavy client bundle
   * and this page sits inside it, so the window is not theoretical.
   *
   * Disabling the controls until this flips is the honest fix: the form
   * cannot act before it can act correctly. `useEffect` runs only on the
   * client, after hydration, which is exactly the signal wanted.
   */
  const [hydrated, setHydrated] = useState(false)
  useEffect(() => setHydrated(true), [])
  const busy = pending || !hydrated

  // A reset pressed on the last row of a long table puts its result at the
  // top of the page, out of sight — and the result is the only copy of the
  // password. Bring it into view rather than trusting anyone to scroll.
  useEffect(() => {
    if (notice) noticeRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [notice])

  function run(action: () => Promise<StaffActionResult>, after?: () => void) {
    startTransition(async () => {
      try {
        const result = await action()
        setNotice(result)
        if (result.ok) after?.()
      } catch {
        // A thrown action is a transport or deployment fault, never a
        // "wrong input". Saying so plainly beats a silent no-op, which is
        // what an unhandled rejection in a transition looks like on screen.
        setNotice({ ok: false, message: 'That did not reach the server. Try again.' })
      }
    })
  }

  function onInvite(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    run(
      () => inviteStaff(data),
      () => form.reset(),
    )
  }

  return (
    <>
      <div aria-live="polite" ref={noticeRef}>
        {notice ? (
          <div className={`staff__notice ${notice.ok ? 'staff__notice--ok' : 'staff__notice--bad'}`}>
            <p className="staff__notice-text">{notice.message}</p>
            {notice.credential ? <Credential credential={notice.credential} /> : null}
            <button className="staff__dismiss" onClick={() => setNotice(IDLE)} type="button">
              Dismiss
            </button>
          </div>
        ) : null}
      </div>

      <h2 className="console__subhead">Invite someone</h2>
      <p className="console__sub">
        Creates the account and generates its first password. The password is
        displayed once and stored only as a hash — if it is lost, reset it
        below rather than looking for it.
      </p>

      <form className="staff__invite" onSubmit={onInvite}>
        <label className="staff__field">
          <span className="staff__label">Email</span>
          <input autoComplete="off" name="email" placeholder="person@example.com" required type="email" />
        </label>
        <label className="staff__field">
          <span className="staff__label">Name</span>
          <input autoComplete="off" name="name" placeholder="Their name" type="text" />
        </label>
        <label className="staff__field">
          <span className="staff__label">Editorial</span>
          <select defaultValue="author" name="editorialRole">
            {EDITORIAL_ORDER.map((role) => (
              <option key={role} value={role}>
                {EDITORIAL_LABELS[role]}
              </option>
            ))}
          </select>
        </label>
        <label className="staff__field">
          <span className="staff__label">Commerce</span>
          <select defaultValue="none" name="commerceRole">
            {COMMERCE_ORDER.map((role) => (
              <option key={role} value={role}>
                {COMMERCE_LABELS[role]}
              </option>
            ))}
          </select>
        </label>
        <button className="staff__btn staff__btn--primary" disabled={busy} type="submit">
          {pending ? 'Working…' : 'Invite'}
        </button>
      </form>

      <h2 className="console__subhead">Accounts</h2>

      {members.length === 0 ? (
        <div className="console__empty">
          No staff accounts exist. The first one is minted with
          <code> npm run staff-account -w @now/auth</code>.
        </div>
      ) : (
        <table className="staff__table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Editorial</th>
              <th>Commerce</th>
              <th>Sign-in</th>
              <th aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {members.map((member) => (
              <MemberRow
                // The role selects below hold local state. Keying on the
                // saved roles as well as the id makes React discard that
                // state once a save lands, so the row shows what is in the
                // database rather than what was last typed into it.
                key={`${member.id}:${member.editorialRole}:${member.commerceRole}`}
                busy={busy}
                isSelf={member.email.toLowerCase() === actorEmail.toLowerCase()}
                member={member}
                run={run}
              />
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}

/**
 * The one place a password is put on screen.
 *
 * `readOnly` rather than plain text so it can be selected and copied on a
 * touch device where there is no clipboard permission, and `spellCheck`
 * off because a browser underlining a random string in red reads as an
 * error.
 */
function Credential({ credential }: { credential: { email: string; password: string } }) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      await navigator.clipboard.writeText(credential.password)
      setCopied(true)
    } catch {
      // Clipboard access needs a secure context, which a plain-http staging
      // host is not. The field beside this button is still selectable.
      setCopied(false)
    }
  }

  return (
    <div className="staff__credential">
      <span className="staff__credential-who">{credential.email}</span>
      <input
        aria-label={`Generated password for ${credential.email}`}
        className="staff__credential-value"
        onFocus={(event) => event.currentTarget.select()}
        readOnly
        spellCheck={false}
        value={credential.password}
      />
      <button className="staff__btn" onClick={copy} type="button">
        {copied ? 'Copied' : 'Copy'}
      </button>
    </div>
  )
}

type RowProps = {
  member: StaffMember
  isSelf: boolean
  busy: boolean
  run: (action: () => Promise<StaffActionResult>, after?: () => void) => void
}

function MemberRow({ busy, isSelf, member, run }: RowProps) {
  const [editorial, setEditorial] = useState<string>(member.editorialRole)
  const [commerce, setCommerce] = useState<string>(member.commerceRole)
  const dirty = editorial !== member.editorialRole || commerce !== member.commerceRole

  // Mirrors the server's rule so the button is not offered before it is
  // refused. `actions.ts` enforces it; this only saves the round trip.
  const wouldDemoteSelf = isSelf && editorial !== 'admin'
  const locked = member.lockedForMinutes > 0

  return (
    <tr>
      <td>
        {member.name ?? <span className="console__muted">—</span>}
        {isSelf ? <span className="staff__you">you</span> : null}
      </td>
      <td>{member.email}</td>
      <td>
        <select
          aria-label={`Editorial role for ${member.email}`}
          disabled={busy}
          onChange={(event) => setEditorial(event.target.value)}
          value={editorial}
        >
          {EDITORIAL_ORDER.map((role) => (
            <option key={role} value={role}>
              {EDITORIAL_LABELS[role]}
            </option>
          ))}
        </select>
      </td>
      <td>
        <select
          aria-label={`Commerce role for ${member.email}`}
          disabled={busy}
          onChange={(event) => setCommerce(event.target.value)}
          value={commerce}
        >
          {COMMERCE_ORDER.map((role) => (
            <option key={role} value={role}>
              {COMMERCE_LABELS[role]}
            </option>
          ))}
        </select>
      </td>
      <td>
        <SignInState member={member} />
      </td>
      <td className="staff__actions">
        {dirty ? (
          <button
            className="staff__btn staff__btn--primary"
            disabled={busy || wouldDemoteSelf}
            onClick={() => run(() => changeRoles(member.id, editorial, commerce))}
            title={
              wouldDemoteSelf
                ? 'You cannot remove your own administrator role.'
                : undefined
            }
            type="button"
          >
            Save
          </button>
        ) : null}
        {locked || member.failedAttempts > 0 ? (
          <button
            className="staff__btn"
            disabled={busy}
            onClick={() => run(() => unlockAccount(member.id))}
            type="button"
          >
            Unlock
          </button>
        ) : null}
        <button
          className="staff__btn"
          disabled={busy}
          onClick={() => run(() => resetPassword(member.id))}
          type="button"
        >
          {member.hasCredential ? 'Reset password' : 'Set password'}
        </button>
      </td>
    </tr>
  )
}

/**
 * Whether this person can actually get in, in one cell.
 *
 * Three distinct states that look alike from the database and are very
 * different to the human: no credential at all (invited by a route that
 * never set one — nothing here creates that, but the CLI and old rows can),
 * locked out, and fine.
 */
function SignInState({ member }: { member: StaffMember }) {
  if (!member.hasCredential) {
    return (
      <span className="console__pill staff__pill--none" title="No password is set, so this account cannot sign in.">
        no password
      </span>
    )
  }
  if (member.lockedForMinutes > 0) {
    return (
      <span
        className="console__pill console__pill--expired"
        title={`${member.failedAttempts} failed attempts. Clears on its own, or unlock now.`}
      >
        locked · {member.lockedForMinutes} min
      </span>
    )
  }
  if (member.failedAttempts > 0) {
    return (
      <span className="console__pill" title="Counts towards a lockout at 8.">
        {member.failedAttempts} failed
      </span>
    )
  }
  return <span className="console__muted">ok</span>
}
