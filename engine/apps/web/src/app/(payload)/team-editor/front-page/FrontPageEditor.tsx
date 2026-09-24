'use client'

import { useMemo, useState, useTransition } from 'react'

import type { HomeRail } from '@/lib/site'

import { refreshAutoFillPreview, saveFrontPage, searchArticlesByTitle } from './actions'
import type { FrontPageActionResult } from './actions'
import type { ArticleSummary } from './data'
import { bandHoldsStories, bandLabel } from './paths'

/**
 * The front-page editor's whole interaction, client-side — same shape as
 * `platform/sites/[slug]/SiteEditor.tsx` and for the same reason: this
 * renders inside Payload's admin, which does not run without JavaScript, so
 * there is no no-JS visitor to serve with a plain `<form action>` here.
 *
 * State shape mirrors `HomeRail` exactly (`lib/site.ts`) — this component
 * edits the real contract, not a view-model of it, so there is nothing to
 * translate on save.
 */

type Props = {
  siteName: string
  governed: boolean
  ttlSeconds: number
  initialRails: HomeRail[]
  initialSummaries: Record<number, ArticleSummary>
  initialAutoFill: Record<string, ArticleSummary[]>
  readOnly: boolean
}

function Notice({ result, onDismiss }: { result: FrontPageActionResult | null; onDismiss: () => void }) {
  if (!result) return null
  return (
    <div aria-live="polite" className={`fp__notice ${result.ok ? 'fp__notice--ok' : 'fp__notice--bad'}`}>
      <p>{result.message}</p>
      <button className="fp__btn" onClick={onDismiss} type="button">
        Dismiss
      </button>
    </div>
  )
}

function when(iso: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

export function FrontPageEditor({
  siteName,
  governed,
  ttlSeconds,
  initialRails,
  initialSummaries,
  initialAutoFill,
  readOnly,
}: Props) {
  const [bands, setBands] = useState<HomeRail[]>(initialRails)
  const [summaries, setSummaries] = useState<Record<number, ArticleSummary>>(initialSummaries)
  const [autoFill, setAutoFill] = useState<Record<string, ArticleSummary[]>>(initialAutoFill)
  const [queries, setQueries] = useState<Record<number, string>>({})
  const [results, setResults] = useState<Record<number, ArticleSummary[]>>({})
  const [notice, setNotice] = useState<FrontPageActionResult | null>(null)
  const [pending, startTransition] = useTransition()
  const [searching, setSearching] = useState<number | null>(null)
  const [previewNonce, setPreviewNonce] = useState(0)

  function moveBand(i: number, dir: -1 | 1) {
    setBands((prev) => {
      const next = [...prev]
      const j = i + dir
      if (j < 0 || j >= next.length) return prev
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })
  }
  function removeBand(i: number) {
    setBands((prev) => prev.filter((_, idx) => idx !== i))
  }
  function addBand() {
    setBands((prev) => [...prev, { key: '' }])
  }
  function updateBand(i: number, patch: Partial<HomeRail>) {
    setBands((prev) => prev.map((b, idx) => (idx === i ? { ...b, ...patch } : b)))
  }

  function pinArticle(bandIndex: number, article: ArticleSummary) {
    setSummaries((prev) => ({ ...prev, [article.id]: article }))
    setBands((prev) =>
      prev.map((b, idx) => {
        if (idx !== bandIndex) return b
        const pins = b.pins ?? []
        if (pins.includes(article.id)) return b
        return { ...b, pins: [...pins, article.id] }
      }),
    )
    setResults((prev) => ({ ...prev, [bandIndex]: [] }))
    setQueries((prev) => ({ ...prev, [bandIndex]: '' }))
  }
  function unpinArticle(bandIndex: number, articleId: number) {
    setBands((prev) =>
      prev.map((b, idx) => (idx === bandIndex ? { ...b, pins: (b.pins ?? []).filter((id) => id !== articleId) } : b)),
    )
  }
  function movePin(bandIndex: number, i: number, dir: -1 | 1) {
    setBands((prev) =>
      prev.map((b, idx) => {
        if (idx !== bandIndex) return b
        const pins = [...(b.pins ?? [])]
        const j = i + dir
        if (j < 0 || j >= pins.length) return b
        ;[pins[i], pins[j]] = [pins[j], pins[i]]
        return { ...b, pins }
      }),
    )
  }

  function runSearch(bandIndex: number) {
    const q = (queries[bandIndex] ?? '').trim()
    if (q.length < 2) {
      setResults((prev) => ({ ...prev, [bandIndex]: [] }))
      return
    }
    setSearching(bandIndex)
    startTransition(async () => {
      try {
        const found = await searchArticlesByTitle(q)
        setResults((prev) => ({ ...prev, [bandIndex]: found }))
      } finally {
        setSearching(null)
      }
    })
  }

  function refreshAutoFill(bandIndex: number, key: string, pins: number[]) {
    startTransition(async () => {
      const preview = await refreshAutoFillPreview(key, pins)
      setAutoFill((prev) => ({ ...prev, [key]: preview }))
    })
  }

  function onSave() {
    startTransition(async () => {
      try {
        const result = await saveFrontPage(bands)
        setNotice(result)
        if (result.ok) setPreviewNonce((n) => n + 1)
      } catch {
        setNotice({ ok: false, message: 'That did not reach the server. Try again.' })
      }
    })
  }

  const previewSrc = useMemo(() => (previewNonce === 0 ? '/' : `/?fp-preview=${previewNonce}`), [previewNonce])

  return (
    <div className="fp">
      <p className="fp__sub">
        {governed
          ? `The order below is what ${siteName}'s home page reads from the registry today.`
          : `${siteName}'s home page has never had its band order saved from here — the order ` +
            'below is a starting scaffold, not a claim about what is live. Save to start governing it.'}
      </p>
      <p className="fp__ttl">
        Saves are live for readers within <strong>{ttlSeconds}</strong> seconds — that is how long
        the home page's own read of this row is cached for.
      </p>

      <Notice result={notice} onDismiss={() => setNotice(null)} />

      <ol className="fp__bands">
        {bands.map((band, i) => {
          const holdsStories = bandHoldsStories(band.key || '')
          const pins = band.pins ?? []
          return (
            <li className="fp__band" key={i}>
              <div className="fp__band-head">
                <span className="fp__band-index">{i + 1}</span>
                <div className="fp__band-fields">
                  <input
                    aria-label={`Band ${i + 1} key`}
                    disabled={readOnly}
                    onChange={(e) => updateBand(i, { key: e.target.value })}
                    placeholder="band key, e.g. department:dining"
                    type="text"
                    value={band.key}
                  />
                  <span className="fp__band-label">{bandLabel(band.key || '(empty)')}</span>
                  <input
                    aria-label={`Band ${i + 1} label override`}
                    disabled={readOnly}
                    onChange={(e) => updateBand(i, { label: e.target.value })}
                    placeholder="label override (optional)"
                    type="text"
                    value={band.label ?? ''}
                  />
                </div>
                {!readOnly && (
                  <div className="fp__row-actions">
                    <button className="fp__btn" disabled={i === 0} onClick={() => moveBand(i, -1)} title="Move up" type="button">
                      ↑
                    </button>
                    <button
                      className="fp__btn"
                      disabled={i === bands.length - 1}
                      onClick={() => moveBand(i, 1)}
                      title="Move down"
                      type="button"
                    >
                      ↓
                    </button>
                    <button className="fp__btn fp__btn--danger" onClick={() => removeBand(i)} title="Remove band" type="button">
                      Remove
                    </button>
                  </div>
                )}
              </div>

              {!holdsStories ? (
                <p className="fp__note">
                  This band lists areas, not stories — pinning does not apply to it.
                </p>
              ) : (
                <div className="fp__band-body">
                  <div className="fp__pins">
                    <p className="fp__pins-label">Pinned, in order</p>
                    {pins.length === 0 ? (
                      <p className="fp__empty">
                        <em>Nothing pinned.</em> This band fills entirely from the auto-fill below.
                      </p>
                    ) : (
                      <ul className="fp__pin-list">
                        {pins.map((id, pi) => {
                          const summary = summaries[id]
                          return (
                            <li className="fp__pin" key={id}>
                              <span className="fp__pin-title">{summary ? summary.title : `Article ${id}`}</span>
                              {summary ? <span className="fp__pin-status">{summary.status}</span> : null}
                              {!readOnly && (
                                <span className="fp__row-actions">
                                  <button
                                    className="fp__btn"
                                    disabled={pi === 0}
                                    onClick={() => movePin(i, pi, -1)}
                                    title="Move up"
                                    type="button"
                                  >
                                    ↑
                                  </button>
                                  <button
                                    className="fp__btn"
                                    disabled={pi === pins.length - 1}
                                    onClick={() => movePin(i, pi, 1)}
                                    title="Move down"
                                    type="button"
                                  >
                                    ↓
                                  </button>
                                  <button
                                    className="fp__btn fp__btn--danger"
                                    onClick={() => unpinArticle(i, id)}
                                    title="Unpin"
                                    type="button"
                                  >
                                    Unpin
                                  </button>
                                </span>
                              )}
                            </li>
                          )
                        })}
                      </ul>
                    )}

                    {!readOnly && (
                      <div className="fp__search">
                        <input
                          aria-label={`Find a story for band ${i + 1}`}
                          onChange={(e) => setQueries((prev) => ({ ...prev, [i]: e.target.value }))}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              runSearch(i)
                            }
                          }}
                          placeholder="Find a story by headline…"
                          type="search"
                          value={queries[i] ?? ''}
                        />
                        <button className="fp__btn" onClick={() => runSearch(i)} type="button">
                          {searching === i ? 'Searching…' : 'Search'}
                        </button>
                      </div>
                    )}
                    {(results[i]?.length ?? 0) > 0 && (
                      <ul className="fp__search-results">
                        {results[i].map((a) => (
                          <li key={a.id}>
                            <span>{a.title}</span>
                            <span className="fp__pin-status">{a.status}</span>
                            <button className="fp__btn" onClick={() => pinArticle(i, a)} type="button">
                              Pin here
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <div className="fp__autofill">
                    <p className="fp__pins-label">
                      Fills automatically after the pins above{' '}
                      <span className="fp__muted">(approximate — recency-ordered, not the engine's own ranking)</span>
                    </p>
                    <ul className="fp__autofill-list">
                      {(autoFill[band.key] ?? []).length === 0 ? (
                        <li className="fp__empty">
                          <em>Nothing to show yet for this band.</em>
                        </li>
                      ) : (
                        (autoFill[band.key] ?? []).map((a) => (
                          <li key={a.id}>
                            <span>{a.title}</span>
                            <span className="fp__muted">{when(a.publishedAt)}</span>
                          </li>
                        ))
                      )}
                    </ul>
                    {!readOnly && (
                      <button className="fp__btn" onClick={() => refreshAutoFill(i, band.key, pins)} type="button">
                        Refresh preview
                      </button>
                    )}
                  </div>
                </div>
              )}
            </li>
          )
        })}
      </ol>

      {!readOnly && (
        <div className="fp__row-actions fp__row-actions--main">
          <button className="fp__btn" onClick={addBand} type="button">
            Add band
          </button>
          <button className="fp__btn fp__btn--primary" disabled={pending} onClick={onSave} type="submit">
            {pending ? 'Saving…' : 'Save order'}
          </button>
        </div>
      )}

      <section className="fp__preview">
        <div className="fp__preview-head">
          <p className="fp__pins-label">The real home page</p>
          <button className="fp__btn" onClick={() => setPreviewNonce((n) => n + 1)} type="button">
            Reload preview
          </button>
        </div>
        <iframe className="fp__preview-frame" key={previewSrc} src={previewSrc} title={`${siteName} home page preview`} />
      </section>
    </div>
  )
}
