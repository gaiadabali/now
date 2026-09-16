'use client'

import { useAuth, useTheme } from '@payloadcms/ui'
import { useEffect, useRef, useState } from 'react'

/**
 * The account menu: profile, appearance, sign out — under the avatar.
 *
 * **Payload's avatar is not a menu.** It is a plain `<Link>` straight to the
 * account page, so there was nowhere to hang anything off it, and the only
 * visible way to sign out was the unlabelled arrow at the foot of the nav.
 * This replaces the link with a real menu and hides Payload's (see
 * `.app-header__account` in styles/admin.css).
 *
 * Registered in `admin.components.actions`, which renders into the app
 * header beside where the avatar was.
 *
 * A CLIENT component on purpose. `useAuth` and `useTheme` are Payload's own
 * providers, already mounted by the admin's root layout, so the theme choice
 * goes through the same path as the one on the account screen — it persists
 * in Payload's cookie and survives a reload. A hand-rolled toggle writing
 * its own storage key would drift from that within a release.
 *
 * `autoMode` is a third state, not a third theme: Payload stores light/dark
 * explicitly and treats "no stored preference" as follow-the-system. So the
 * menu offers three choices and only two of them are values.
 */

type MenuUser = { email?: string; name?: string; role?: string } | null | undefined

const ROLE_LABEL: Record<string, string> = {
  admin: 'Administrator',
  editor: 'Editor',
  author: 'Author — drafts only',
  none: 'No editorial access',
}

function initialOf(user: MenuUser): string {
  const source = user?.name?.trim() || user?.email?.trim() || ''
  const first = [...source][0]
  return first ? first.toUpperCase() : '·'
}

export function AccountMenu() {
  const { user } = useAuth() as { user: MenuUser }
  const { autoMode, setTheme, theme } = useTheme()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  // Close on outside click and on Escape. Without both, a menu opened by
  // accident can only be dismissed by clicking its own trigger again, which
  // people do not discover.
  useEffect(() => {
    if (!open) return

    function onPointerDown(event: MouseEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }

    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  if (!user) return null

  const role = user.role ? (ROLE_LABEL[user.role] ?? user.role) : null
  // `autoMode` wins: with no stored preference Payload follows the system,
  // and `theme` still reports whichever one that resolved to.
  const current = autoMode ? 'auto' : theme

  function choose(next: 'auto' | 'dark' | 'light') {
    // `setTheme('auto')` is how Payload clears the stored preference; its
    // own account-screen control does the same.
    setTheme(next as Parameters<typeof setTheme>[0])
    setOpen(false)
  }

  return (
    <div className="now-account" ref={root}>
      <button
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="Account menu"
        className="now-account__trigger"
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        type="button"
      >
        <span aria-hidden="true" className="now-avatar">
          {initialOf(user)}
        </span>
      </button>

      {open ? (
        <div className="now-account__menu" role="menu">
          <div className="now-account__who">
            <span className="now-account__name">{user.name?.trim() || user.email}</span>
            {user.name?.trim() && user.email ? (
              <span className="now-account__email">{user.email}</span>
            ) : null}
            {role ? <span className="now-account__role">{role}</span> : null}
          </div>

          <a className="now-account__item" href="/team-editor/account" role="menuitem">
            Profile
          </a>

          <div className="now-account__section">
            <span className="now-account__section-label">Appearance</span>
            <div className="now-account__themes">
              {(['auto', 'light', 'dark'] as const).map((option) => (
                <button
                  aria-checked={current === option}
                  className="now-account__theme"
                  key={option}
                  onClick={() => choose(option)}
                  role="menuitemradio"
                  type="button"
                >
                  {option === 'auto' ? 'System' : option === 'light' ? 'Light' : 'Dark'}
                </button>
              ))}
            </div>
          </div>

          <a
            className="now-account__item now-account__item--out"
            href="/team-editor/logout"
            role="menuitem"
          >
            Sign out
          </a>
        </div>
      ) : null}
    </div>
  )
}
