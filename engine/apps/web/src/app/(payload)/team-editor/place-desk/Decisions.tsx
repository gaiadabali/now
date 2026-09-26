'use client'

import { useActionState, useEffect, useRef, useState, type MouseEvent } from 'react'

import { bulkJunk, decide, merge, type DeskResult } from './actions'

/**
 * The desk's controls. Each is a plain `<form>` posting to a server action,
 * so the result the server returns is shown verbatim: the count that was
 * written, or the CMS's own reason for refusing (the approval gate, a
 * validation error). Buttons name their outcome ("Approve", "Mark as junk")
 * per the design system's copy rules.
 *
 * Forms with several outcomes carry the choice in a hidden input the
 * clicked button writes, rather than relying on the submit button's own
 * name/value reaching the action: that did not arrive reliably through
 * React's form action here (measured: the approve press posted an empty
 * decision).
 */

/** A hidden input a button writes its value into, synchronously, on click. */
function useChoice(name: string) {
  const ref = useRef<HTMLInputElement>(null)
  const input = <input ref={ref} type="hidden" name={name} defaultValue="" />
  const choose = (value: string) => (_e: MouseEvent<HTMLButtonElement>) => {
    if (ref.current) ref.current.value = value
  }
  return { input, choose }
}

function Note({ state }: { state: DeskResult | null }) {
  if (!state) return null
  return (
    <p className={`classify__decide-note${state.ok ? '' : ' classify__decide-note--error'}`} role="status">
      {state.ok ? state.message : state.error}
    </p>
  )
}

export function DecisionButtons({
  id,
  status,
  approveBlockedBecause,
}: {
  id: number
  status: string
  approveBlockedBecause: string | null
}) {
  const [state, action, busy] = useActionState<DeskResult | null, FormData>(decide, null)
  const { input, choose } = useChoice('decision')
  return (
    <form action={action} className="place-desk__decide">
      <input type="hidden" name="id" value={id} />
      {input}
      {status === 'pending_review' ? (
        <div className="place-desk__buttons">
          <button
            type="submit"
            onClick={choose('approve')}
            value="approve"
            className="classify__btn classify__btn--primary"
            disabled={busy || approveBlockedBecause !== null}
            aria-describedby={approveBlockedBecause ? `approve-why-${id}` : undefined}
          >
            Approve
          </button>
          <button type="submit" onClick={choose('keep')} value="keep" className="classify__btn" disabled={busy}>
            Keep, decide later
          </button>
          <button type="submit" onClick={choose('junk')} value="junk" className="classify__btn classify__btn--quiet" disabled={busy}>
            Mark as junk
          </button>
        </div>
      ) : (
        <div className="place-desk__buttons">
          <button type="submit" onClick={choose('reopen')} value="reopen" className="classify__btn" disabled={busy}>
            {status === 'active' ? 'Take down, back to the queue' : 'Put back in the queue'}
          </button>
        </div>
      )}
      {status === 'pending_review' && approveBlockedBecause ? (
        <p id={`approve-why-${id}`} className="place-desk__hint">
          {approveBlockedBecause}
        </p>
      ) : null}
      <Note state={state} />
    </form>
  )
}

export type SubtypeGroupOption = { type: string; label: string; subtypes: Array<{ slug: string; label: string }> }

export function TypeForm({ id, groups, current }: { id: number; groups: SubtypeGroupOption[]; current: string | null }) {
  const [state, action, busy] = useActionState<DeskResult | null, FormData>(decide, null)
  const known = groups.some((g) => g.subtypes.some((s) => s.slug === current))
  return (
    <form action={action} className="place-desk__inline-form">
      <input type="hidden" name="id" value={id} />
      <input type="hidden" name="decision" value="type" />
      <label className="classify__visually-hidden" htmlFor={`subtype-${id}`}>
        Kind of place
      </label>
      <select id={`subtype-${id}`} name="subtype" className="classify__select" defaultValue={known ? current ?? '' : ''} required>
        <option value="" disabled>
          Choose…
        </option>
        {groups.map((g) => (
          <optgroup key={g.type} label={g.label}>
            {g.subtypes.map((s) => (
              <option key={s.slug} value={s.slug}>
                {s.label}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      <button type="submit" className="classify__btn" disabled={busy || groups.length === 0}>
        Save kind
      </button>
      <Note state={state} />
    </form>
  )
}

export type AreaOptionItem = { slug: string; label: string; parentLabel: string | null }

export function AreaForm({
  id,
  home,
  elsewhere,
  current,
  homeLabel,
}: {
  id: number
  home: AreaOptionItem[]
  elsewhere: AreaOptionItem[]
  current: string | null
  homeLabel: string
}) {
  const [state, action, busy] = useActionState<DeskResult | null, FormData>(decide, null)
  const label = (a: AreaOptionItem) => (a.parentLabel ? `${a.label} — ${a.parentLabel}` : a.label)
  return (
    <form action={action} className="place-desk__inline-form">
      <input type="hidden" name="id" value={id} />
      <input type="hidden" name="decision" value="area" />
      <label className="classify__visually-hidden" htmlFor={`area-${id}`}>
        Area
      </label>
      <select id={`area-${id}`} name="area" className="classify__select" defaultValue={current ?? ''} required>
        <option value="" disabled>
          Choose…
        </option>
        <optgroup label={homeLabel}>
          {home.map((a) => (
            <option key={a.slug} value={a.slug}>
              {label(a)}
            </option>
          ))}
        </optgroup>
        <optgroup label="Elsewhere">
          {elsewhere.map((a) => (
            <option key={a.slug} value={a.slug}>
              {label(a)}
            </option>
          ))}
        </optgroup>
      </select>
      <button type="submit" className="classify__btn" disabled={busy}>
        Save area
      </button>
      <Note state={state} />
    </form>
  )
}

export function MergeButtons({ id, other, otherName }: { id: number; other: number; otherName: string }) {
  const [state, action, busy] = useActionState<DeskResult | null, FormData>(merge, null)
  const { input, choose } = useChoice('direction')
  return (
    <form action={action} className="place-desk__merge">
      <input type="hidden" name="id" value={id} />
      {input}
      <input type="hidden" name="other" value={other} />
      <div className="place-desk__buttons">
        <button type="submit" onClick={choose('into-this')} value="into-this" className="classify__btn" disabled={busy}
          aria-label={`Same place: merge ${otherName} into this one`}>
          Same place, keep this one
        </button>
        <button type="submit" onClick={choose('into-other')} value="into-other" className="classify__btn classify__btn--quiet" disabled={busy}
          aria-label={`Same place: merge this one into ${otherName}`}>
          Same place, keep that one
        </button>
      </div>
      <Note state={state} />
    </form>
  )
}

export function MergeByNumber({ id }: { id: number }) {
  const [state, action, busy] = useActionState<DeskResult | null, FormData>(merge, null)
  return (
    <form action={action} className="place-desk__inline-form">
      <input type="hidden" name="id" value={id} />
      <input type="hidden" name="direction" value="into-this" />
      <label htmlFor={`merge-other-${id}`} className="place-desk__label">
        Place number
      </label>
      <input id={`merge-other-${id}`} name="other" inputMode="numeric" pattern="[0-9]+" className="classify__select place-desk__number" required />
      <button type="submit" value="into-this" className="classify__btn" disabled={busy}>
        Merge it into this one
      </button>
      <Note state={state} />
    </form>
  )
}

export type JunkRow = { id: number; name: string; reason: string; featured: number; articles: number; href: string }

export function BulkJunkForm({ rows, batch }: { rows: JunkRow[]; batch: number }) {
  const [state, action, busy] = useActionState<DeskResult | null, FormData>(bulkJunk, null)
  const [ticked, setTicked] = useState<Set<number>>(() => new Set(rows.map((r) => r.id)))
  // After a press the server re-renders this list without the rows it just
  // wrote. Re-tick the new page rather than remounting, which would also
  // throw away the result line the editor needs to read.
  const idsKey = rows.map((r) => r.id).join(',')
  useEffect(() => {
    setTicked(new Set(idsKey ? idsKey.split(',').map(Number) : []))
  }, [idsKey])
  const toggle = (id: number) =>
    setTicked((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  const all = ticked.size === rows.length
  return (
    <form action={action} className="place-desk__bulk">
      <div className="classify__bulk-row">
        <button type="submit" className="classify__btn classify__btn--primary" disabled={busy || ticked.size === 0}>
          Mark {Math.min(ticked.size, batch)} as junk
        </button>
        <button type="button" className="classify__btn classify__btn--quiet" onClick={() => setTicked(all ? new Set() : new Set(rows.map((r) => r.id)))}>
          {all ? 'Untick all' : 'Tick all'}
        </button>
        <span className="classify__muted">
          Untick anything that is a real place, then open it and choose Keep. At most {batch} per press.
        </span>
      </div>
      <Note state={state} />
      <table>
        <thead>
          <tr>
            <th scope="col" className="place-desk__tick">
              <span className="classify__visually-hidden">Mark as junk</span>
            </th>
            <th scope="col">Name as stored</th>
            <th scope="col">Why it looks like junk</th>
            <th scope="col" className="classify__num">Featured</th>
            <th scope="col" className="classify__num">Stories</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="place-desk__tick">
                <input
                  type="checkbox"
                  name="ids"
                  value={r.id}
                  checked={ticked.has(r.id)}
                  onChange={() => toggle(r.id)}
                  aria-label={`Mark ${r.name} as junk`}
                />
              </td>
              <td>
                <a href={r.href}>{r.name}</a>
              </td>
              <td className="classify__muted">{r.reason}</td>
              <td className="classify__num">{r.featured}</td>
              <td className="classify__num">{r.articles}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </form>
  )
}
