'use client'

import { useState, useTransition } from 'react'

import type { CityPlace } from '@/lib/queries'

import { attachVenue, detachVenue, searchVenues } from './venuesActions'

/**
 * "Venues belonging to this organisation" — search this city's places by
 * name, attach one, or detach one already linked. See `venuesActions.ts`
 * for why this writes through Payload rather than SQL, and what gates it.
 */
export function VenuesPanel({ orgId, orgName, initialVenues }: { orgId: string; orgName: string; initialVenues: CityPlace[] }) {
  const [venues, setVenues] = useState(initialVenues)
  const [term, setTerm] = useState('')
  const [results, setResults] = useState<CityPlace[] | null>(null)
  const [notice, setNotice] = useState<{ ok: boolean; message: string } | null>(null)
  const [pending, startTransition] = useTransition()

  function onSearch(event: React.FormEvent) {
    event.preventDefault()
    startTransition(async () => {
      setResults(await searchVenues(term))
    })
  }

  function onAttach(place: CityPlace) {
    startTransition(async () => {
      const result = await attachVenue(orgId, place.id)
      setNotice(result)
      if (result.ok) {
        setVenues((prev) => [...prev.filter((v) => v.id !== place.id), { ...place, orgId }].sort((a, b) => a.name.localeCompare(b.name)))
        setResults((prev) => prev?.filter((r) => r.id !== place.id) ?? null)
      }
    })
  }

  function onDetach(place: CityPlace) {
    startTransition(async () => {
      const result = await detachVenue(orgId, place.id)
      setNotice(result)
      if (result.ok) {
        setVenues((prev) => prev.filter((v) => v.id !== place.id))
      }
    })
  }

  return (
    <section id="venues">
      <h2 className="console__subhead">Venues belonging to {orgName}</h2>
      <p className="console__sub">
        A partnership above only changes what readers see once a real venue is linked here — every
        mention of a linked venue picks up this organisation&rsquo;s partnership automatically, with
        no article edited.
      </p>

      {notice ? (
        <div aria-live="polite" className={`platform__notice ${notice.ok ? 'platform__notice--ok' : 'platform__notice--bad'}`}>
          <p>{notice.message}</p>
          <button className="platform__btn" onClick={() => setNotice(null)} type="button">
            Dismiss
          </button>
        </div>
      ) : null}

      {venues.length === 0 ? (
        <div className="console__empty">No venue is linked to this organisation yet.</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Venue</th>
              <th>Type</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {venues.map((v) => (
              <tr key={v.id}>
                <td>{v.name}</td>
                <td>{v.type ?? '—'}</td>
                <td>
                  <button className="platform__btn platform__btn--danger" disabled={pending} onClick={() => onDetach(v)} type="button">
                    Unlink
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <form className="platform__row-actions" onSubmit={onSearch} style={{ marginTop: '0.9rem' }}>
        <input
          aria-label="Search venues by name"
          onChange={(e) => setTerm(e.target.value)}
          placeholder="Find a venue by name to link…"
          type="search"
          value={term}
        />
        <button className="platform__btn" disabled={pending || !term.trim()} type="submit">
          Search
        </button>
      </form>

      {results ? (
        results.length === 0 ? (
          <p className="console__sub">No venue matches &ldquo;{term}&rdquo; in this city.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Venue</th>
                <th>Type</th>
                <th>Currently linked to</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {results.map((r) => (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td>{r.type ?? '—'}</td>
                  <td>
                    {r.orgId === orgId ? (
                      <span className="console__muted">this organisation</span>
                    ) : r.orgId ? (
                      <span className="console__muted">another organisation</span>
                    ) : (
                      <span className="console__muted">nothing</span>
                    )}
                  </td>
                  <td>
                    {r.orgId === orgId ? null : (
                      <button className="platform__btn ws4-btn--primary" disabled={pending} onClick={() => onAttach(r)} type="button">
                        Link
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )
      ) : null}
    </section>
  )
}
