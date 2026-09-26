'use client'

import { useEffect, useState, useTransition } from 'react'

import { MODULE_LABELS } from '@/lib/moduleNames'
import type { ModuleName } from '@/lib/moduleNames'
import type { HomeRail, NavItem, SiteConfig } from '@/lib/site'

import { saveBrand, saveHomeRails, saveModules, saveNav } from './actions'
import type { PlatformActionResult } from './actions'

/**
 * The whole edit screen's interaction, in one client component — same shape
 * as `team-editor/staff/StaffConsole.tsx` and for the same reason: this
 * renders inside Payload's admin, which does not run at all without
 * JavaScript, so there is no no-JS visitor to serve with a plain `<form
 * action>` post here the way `(site)/account` needs one.
 *
 * Three independent forms — `NavForm`, `BrandForm`, `RailsForm` — each with
 * its own notice and its own pending state, because saving one must not
 * discard feedback from another still on screen, and a slow nav save should
 * not disable the brand form. Exported separately, not as one aggregate
 * component: `page.tsx` interleaves each form directly under its own
 * heading and its own registry-vs-file comparison, rather than grouping all
 * three edit forms together below three separate comparisons — the whole
 * point of showing the comparison is for it to sit next to the control that
 * changes the winner.
 *
 * Every save goes through a server action that re-checks `requireStaffAdmin()`
 * and re-validates with `lib/site.ts`'s own predicates. Nothing client-side
 * here is a permission check or the real validation; disabling the buttons on
 * an obviously-empty nav is courtesy, so an editor is not surprised by a
 * refusal for a reason they could see coming.
 */

function Notice({ result, onDismiss }: { result: PlatformActionResult | null; onDismiss: () => void }) {
  if (!result) return null
  return (
    <div aria-live="polite" className={`platform__notice ${result.ok ? 'platform__notice--ok' : 'platform__notice--bad'}`}>
      <p>{result.message}</p>
      <button className="platform__btn" onClick={onDismiss} type="button">
        Dismiss
      </button>
    </div>
  )
}

/* ------------------------------------------------------------------ nav */

export function NavForm({ slug, siteName, initial }: { slug: string; siteName: string; initial: NavItem[] }) {
  const [items, setItems] = useState<NavItem[]>(initial.length > 0 ? initial : [{ label: '', href: '' }])
  const [notice, setNotice] = useState<PlatformActionResult | null>(null)
  const [pending, startTransition] = useTransition()

  function update(i: number, patch: Partial<NavItem>) {
    setItems((prev) => prev.map((item, idx) => (idx === i ? { ...item, ...patch } : item)))
  }
  function remove(i: number) {
    setItems((prev) => prev.filter((_, idx) => idx !== i))
  }
  function move(i: number, dir: -1 | 1) {
    setItems((prev) => {
      const next = [...prev]
      const j = i + dir
      if (j < 0 || j >= next.length) return prev
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })
  }
  function add() {
    setItems((prev) => [...prev, { label: '', href: '' }])
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    // Trim before sending: a label or href that is only whitespace passes an
    // `!== ''` check and fails `navFrom`'s trimmed check server-side, which
    // would report a rejection for something that looked filled in on screen.
    const trimmed = items.map((item) => ({ label: item.label.trim(), href: item.href.trim() }))
    startTransition(async () => {
      try {
        setNotice(await saveNav(slug, trimmed))
      } catch {
        setNotice({ ok: false, message: 'That did not reach the server. Try again.' })
      }
    })
  }

  return (
    <section>
      <p className="platform__sub">
        The masthead links for {siteName}, in order. Saving an empty list is refused — an editor
        who means to stop governing this removes the row entirely rather than emptying it; a
        genuinely empty nav would leave the site with no navigation, where an untouched value falls
        back to the config file.
      </p>
      <Notice result={notice} onDismiss={() => setNotice(null)} />
      <form className="platform__form" onSubmit={onSubmit}>
        <ul className="platform__nav-list">
          {items.map((item, i) => (
            <li className="platform__nav-item" key={i}>
              <input
                aria-label={`Nav item ${i + 1} label`}
                onChange={(e) => update(i, { label: e.target.value })}
                placeholder="Label"
                type="text"
                value={item.label}
              />
              <input
                aria-label={`Nav item ${i + 1} link`}
                onChange={(e) => update(i, { href: e.target.value })}
                placeholder="/section"
                type="text"
                value={item.href}
              />
              <div className="platform__row-actions">
                <button disabled={i === 0} onClick={() => move(i, -1)} title="Move up" type="button" className="platform__btn">
                  ↑
                </button>
                <button
                  disabled={i === items.length - 1}
                  onClick={() => move(i, 1)}
                  title="Move down"
                  type="button"
                  className="platform__btn"
                >
                  ↓
                </button>
                <button onClick={() => remove(i)} title="Remove" type="button" className="platform__btn platform__btn--danger">
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
        <div className="platform__row-actions">
          <button className="platform__btn" onClick={add} type="button">
            Add item
          </button>
          <button className="platform__btn platform__btn--primary" disabled={pending} type="submit">
            {pending ? 'Saving…' : 'Save nav'}
          </button>
        </div>
      </form>
    </section>
  )
}

/* ---------------------------------------------------------------- brand */

const BRAND_FIELDS: Array<{ key: keyof SiteConfig['brand']; label: string }> = [
  { key: 'logo', label: 'Logo (path)' },
  { key: 'logoAlt', label: 'Logo alt text' },
  { key: 'favicon', label: 'Favicon (path)' },
  { key: 'appleIcon', label: 'Apple touch icon (path)' },
]

export function BrandForm({
  slug,
  siteName,
  initial,
  placeholders,
}: {
  slug: string
  siteName: string
  initial: Partial<SiteConfig['brand']>
  placeholders: SiteConfig['brand'] | null
}) {
  const [values, setValues] = useState<Record<string, string>>({
    logo: initial.logo ?? '',
    logoAlt: initial.logoAlt ?? '',
    favicon: initial.favicon ?? '',
    appleIcon: initial.appleIcon ?? '',
  })
  const [notice, setNotice] = useState<PlatformActionResult | null>(null)
  const [pending, startTransition] = useTransition()

  function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    startTransition(async () => {
      try {
        setNotice(await saveBrand(slug, values))
      } catch {
        setNotice({ ok: false, message: 'That did not reach the server. Try again.' })
      }
    })
  }

  return (
    <section>
      <p className="platform__sub">
        Leave a field blank to keep it governed by the config file — that is not the same as an
        empty string, and saving does not write one; a blank field is simply left out of what this
        console governs (see the placeholder for what the file currently supplies).
      </p>
      <Notice result={notice} onDismiss={() => setNotice(null)} />
      <form className="platform__form" onSubmit={onSubmit}>
        <div className="platform__fields">
          {BRAND_FIELDS.map(({ key, label }) => (
            <label className="platform__field" key={key}>
              <span className="platform__field-label">{label}</span>
              <input
                onChange={(e) => setValues((prev) => ({ ...prev, [key]: e.target.value }))}
                placeholder={placeholders?.[key] ?? ''}
                type="text"
                value={values[key]}
              />
            </label>
          ))}
        </div>
        <div className="platform__row-actions">
          <button className="platform__btn platform__btn--primary" disabled={pending} type="submit">
            {pending ? 'Saving…' : `Save marks for ${siteName}`}
          </button>
        </div>
      </form>
    </section>
  )
}

/* -------------------------------------------------------------- modules */

/**
 * `enabled_modules` (P0.3) toggles — one checkbox per known module, in the
 * fixed order `MODULE_LIST` gives (`lib/moduleNames.ts`), so the screen never
 * shows a flag `getSiteConfig()`/`moduleEnabled()` would not also recognise.
 * Saving always writes the whole set (checked = in the array), the same
 * "replace, don't merge" rule `saveModules` and `updateSiteEnabledModules`
 * (`lib/queries.ts`) follow — there is no per-module save button, unlike nav
 * or rails, because there is nothing per-item to reorder or validate.
 */
export function ModulesForm({
  slug,
  siteName,
  all,
  initial,
}: {
  slug: string
  siteName: string
  all: ModuleName[]
  initial: ModuleName[]
}) {
  const [checked, setChecked] = useState<Set<ModuleName>>(new Set(initial))
  const [notice, setNotice] = useState<PlatformActionResult | null>(null)
  const [pending, startTransition] = useTransition()

  function toggle(module: ModuleName) {
    setChecked((prev) => {
      const next = new Set(prev)
      if (next.has(module)) next.delete(module)
      else next.add(module)
      return next
    })
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    startTransition(async () => {
      try {
        setNotice(await saveModules(slug, Array.from(checked)))
      } catch {
        setNotice({ ok: false, message: 'That did not reach the server. Try again.' })
      }
    })
  }

  return (
    <section>
      <p className="platform__sub">
        Every new reader surface (itineraries, reading state, print, offers, the newsletter, the
        partner portal) ships behind one of these flags and stays off until toggled on here — an
        unchecked module 404s its routes and hides its dashboard panels, the same way a route that
        was never built would.
      </p>
      <Notice result={notice} onDismiss={() => setNotice(null)} />
      <form className="platform__form" onSubmit={onSubmit}>
        <ul className="platform__nav-list">
          {all.map((module) => (
            <li className="platform__nav-item" key={module}>
              <label>
                <input
                  checked={checked.has(module)}
                  onChange={() => toggle(module)}
                  type="checkbox"
                />
                {' '}
                {MODULE_LABELS[module]} <code>({module})</code>
              </label>
            </li>
          ))}
        </ul>
        <div className="platform__row-actions">
          <button className="platform__btn platform__btn--primary" disabled={pending} type="submit">
            {pending ? 'Saving…' : `Save modules for ${siteName}`}
          </button>
        </div>
      </form>
    </section>
  )
}

/* ---------------------------------------------------------------- rails */

export function RailsForm({ slug, siteName, initial }: { slug: string; siteName: string; initial: HomeRail[] }) {
  const [items, setItems] = useState<HomeRail[]>(initial)
  const [notice, setNotice] = useState<PlatformActionResult | null>(null)
  const [pending, startTransition] = useTransition()

  function update(i: number, patch: Partial<HomeRail>) {
    setItems((prev) => prev.map((item, idx) => (idx === i ? { ...item, ...patch } : item)))
  }
  function remove(i: number) {
    setItems((prev) => prev.filter((_, idx) => idx !== i))
  }
  function move(i: number, dir: -1 | 1) {
    setItems((prev) => {
      const next = [...prev]
      const j = i + dir
      if (j < 0 || j >= next.length) return prev
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })
  }
  function add() {
    setItems((prev) => [...prev, { key: '' }])
  }

  function onSubmit(event: React.FormEvent) {
    event.preventDefault()
    const trimmed = items.map((item) => ({
      key: item.key.trim(),
      ...(item.label?.trim() ? { label: item.label.trim() } : {}),
      ...(item.note?.trim() ? { note: item.note.trim() } : {}),
      ...(item.limit ? { limit: item.limit } : {}),
    }))
    startTransition(async () => {
      try {
        setNotice(await saveHomeRails(slug, trimmed))
      } catch {
        setNotice({ ok: false, message: 'That did not reach the server. Try again.' })
      }
    })
  }

  return (
    <section>
      <p className="platform__sub">
        Registry-only — there is no config-file equivalent, so nothing reads this yet except this
        screen (S6.3 is what will). Clearing the list is allowed and means &ldquo;let the homepage
        decide its own order&rdquo;, which is what happens today.
      </p>
      <Notice result={notice} onDismiss={() => setNotice(null)} />
      <form className="platform__form" onSubmit={onSubmit}>
        <ul className="platform__nav-list">
          {items.map((item, i) => (
            <li className="platform__nav-item" key={i}>
              <input
                aria-label={`Rail ${i + 1} key`}
                onChange={(e) => update(i, { key: e.target.value })}
                placeholder="key"
                type="text"
                value={item.key}
              />
              <input
                aria-label={`Rail ${i + 1} label override`}
                onChange={(e) => update(i, { label: e.target.value })}
                placeholder="label override (optional)"
                type="text"
                value={item.label ?? ''}
              />
              <div className="platform__row-actions">
                <button disabled={i === 0} onClick={() => move(i, -1)} title="Move up" type="button" className="platform__btn">
                  ↑
                </button>
                <button
                  disabled={i === items.length - 1}
                  onClick={() => move(i, 1)}
                  title="Move down"
                  type="button"
                  className="platform__btn"
                >
                  ↓
                </button>
                <button onClick={() => remove(i)} title="Remove" type="button" className="platform__btn platform__btn--danger">
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
        <div className="platform__row-actions">
          <button className="platform__btn" onClick={add} type="button">
            Add rail
          </button>
          <button className="platform__btn platform__btn--primary" disabled={pending} type="submit">
            {pending ? 'Saving…' : 'Save order'}
          </button>
        </div>
      </form>
    </section>
  )
}
