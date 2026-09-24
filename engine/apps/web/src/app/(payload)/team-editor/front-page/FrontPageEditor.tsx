'use client'

import { useMemo, useState, useTransition } from 'react'

import type { HomeRail } from '@/lib/site'

import { refreshAutoFillPreview, saveFrontPage, searchArticlesByTitle } from './actions'
import type { FrontPageActionResult } from './actions'
import type { ArticleSummary } from './data'
import { addableBandTypes, bandFillDescription, bandLabel, bandPinnable } from './paths'

/**
 * The front-page editor's whole interaction, client-side — same shape as
 * `platform/sites/[slug]/SiteEditor.tsx` and for the same reason: this
 * renders inside Payload's admin, which does not run without JavaScript, so
 * there is no no-JS visitor to serve with a plain `<form action>` here.
 *
 * **Second pass, after the first read as an engineering tool rather than a
 * writer's screen.** Two changes carry the whole rewrite:
 *
 *   1. Every band is a COLLAPSED ROW by default — position, its name in
 *      plain words, how many stories are pinned, and a one-line "then fills
 *      with…". Only one band expands at a time (`expanded`), and its
 *      auto-fill preview is fetched only then, not for all twelve bands on
 *      every load.
 *   2. Nothing renders a raw band `key` as a heading. `bandLabel()` /
 *      `bandFillDescription()` (`paths.ts`) turn every key into the reader's
 *      own words — a department reads as this site's REAL, currently
 *      governed nav label ("Resto & Bars section"), not the internal slug
 *      ("dining") — and adding a band offers a dropdown of those same human
 *      names, with a raw-key text input reachable only through an explicit
 *      "custom" option, clearly marked advanced.
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
  /** `[href-without-slash, label][]` — a `Map` doesn't need to survive a
   * server/client prop boundary when a plain array does the same job with
   * no ambiguity about whether it serialised correctly. */
  navLabelEntries: Array<[string, string]>
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

const CUSTOM_OPTION = '__custom__'

export function FrontPageEditor({
  siteName,
  governed,
  ttlSeconds,
  initialRails,
  initialSummaries,
  navLabelEntries,
  readOnly,
}: Props) {
  const navLabels = useMemo(() => new Map(navLabelEntries), [navLabelEntries])
  const [bands, setBands] = useState<HomeRail[]>(initialRails)
  const [summaries, setSummaries] = useState<Record<number, ArticleSummary>>(initialSummaries)
  const [autoFill, setAutoFill] = useState<Record<number, ArticleSummary[]>>({})
  const [autoFillLoading, setAutoFillLoading] = useState<number | null>(null)
  const [expanded, setExpanded] = useState<number | null>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<ArticleSummary[]>([])
  const [searching, setSearching] = useState(false)
  const [notice, setNotice] = useState<FrontPageActionResult | null>(null)
  const [pending, startTransition] = useTransition()
  const [previewNonce, setPreviewNonce] = useState(0)
  const [addChoice, setAddChoice] = useState<string>('')
  const [customKey, setCustomKey] = useState('')

  const addOptions = useMemo(() => addableBandTypes(navLabels), [navLabels])

  function moveBand(i: number, dir: -1 | 1) {
    setBands((prev) => {
      const next = [...prev]
      const j = i + dir
      if (j < 0 || j >= next.length) return prev
      ;[next[i], next[j]] = [next[j], next[i]]
      return next
    })
    setExpanded((prev) => (prev === i ? i + dir : prev === i + dir ? i : prev))
  }
  function removeBand(i: number) {
    setBands((prev) => prev.filter((_, idx) => idx !== i))
    setExpanded((prev) => (prev === i ? null : prev && prev > i ? prev - 1 : prev))
  }
  function addBand() {
    const key = addChoice === CUSTOM_OPTION ? customKey.trim() : addChoice
    if (!key) return
    setBands((prev) => [...prev, { key }])
    setAddChoice('')
    setCustomKey('')
  }
  function updateBand(i: number, patch: Partial<HomeRail>) {
    setBands((prev) => prev.map((b, idx) => (idx === i ? { ...b, ...patch } : b)))
  }

  function toggleExpand(i: number) {
    const next = expanded === i ? null : i
    setExpanded(next)
    setResults([])
    setQuery('')
    if (next !== null && bandPinnable(bands[next].key) && !(next in autoFill)) {
      loadAutoFill(next)
    }
  }

  function loadAutoFill(i: number) {
    const band = bands[i]
    setAutoFillLoading(i)
    startTransition(async () => {
      try {
        const preview = await refreshAutoFillPreview(band.key, band.pins ?? [])
        setAutoFill((prev) => ({ ...prev, [i]: preview }))
      } finally {
        setAutoFillLoading(null)
      }
    })
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
    setResults([])
    setQuery('')
    // The preview no longer reflects the current pins; drop the cached
    // fetch rather than show a story both pinned and "auto-filled".
    setAutoFill((prev) => {
      const next = { ...prev }
      delete next[bandIndex]
      return next
    })
  }
  function unpinArticle(bandIndex: number, articleId: number) {
    setBands((prev) =>
      prev.map((b, idx) => (idx === bandIndex ? { ...b, pins: (b.pins ?? []).filter((id) => id !== articleId) } : b)),
    )
    setAutoFill((prev) => {
      const next = { ...prev }
      delete next[bandIndex]
      return next
    })
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

  function runSearch() {
    const q = query.trim()
    if (q.length < 2) {
      setResults([])
      return
    }
    setSearching(true)
    startTransition(async () => {
      try {
        setResults(await searchArticlesByTitle(q))
      } finally {
        setSearching(false)
      }
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
          ? `This is the order of ${siteName}'s home page right now.`
          : `${siteName}'s home page is using its built-in order, shown below. Change anything and ` +
            'save, and from then on the home page follows this screen.'}
      </p>
      <p className="fp__ttl">
        Saves are live for readers within <strong>{ttlSeconds}</strong> seconds — that is how long
        the home page's own read of this row is cached for.
      </p>

      <Notice result={notice} onDismiss={() => setNotice(null)} />

      <div className="fp__layout">
        <div className="fp__bands-col">
          <ol className="fp__bands">
            {bands.map((band, i) => {
              const pinnable = bandPinnable(band.key)
              const pins = band.pins ?? []
              const isOpen = expanded === i
              return (
                <li className={`fp__row ${isOpen ? 'fp__row--open' : ''}`} key={i}>
                  <button
                    aria-expanded={isOpen}
                    className="fp__row-summary"
                    onClick={() => toggleExpand(i)}
                    type="button"
                  >
                    <span className="fp__row-pos">{i + 1}</span>
                    <span className="fp__row-main">
                      <span className="fp__row-name">{bandLabel(band.key, navLabels)}</span>
                      <span className="fp__row-meta">
                        {pinnable ? `${pins.length} pinned — ` : ''}
                        then fills with: {bandFillDescription(band.key, navLabels)}
                      </span>
                    </span>
                    <span className="fp__row-chevron" aria-hidden="true">
                      {isOpen ? '−' : '+'}
                    </span>
                  </button>

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

                  {isOpen && (
                    <div className="fp__row-detail">
                      {!readOnly && (
                        <input
                          aria-label={`Label override for ${bandLabel(band.key, navLabels)}`}
                          className="fp__label-override"
                          onChange={(e) => updateBand(i, { label: e.target.value })}
                          placeholder={`Show as “${bandLabel(band.key, navLabels)}” — or type a different heading`}
                          type="text"
                          value={band.label ?? ''}
                        />
                      )}

                      {!pinnable ? (
                        <p className="fp__note">
                          {band.key === 'for-you'
                            ? 'This band is personal to each reader — pinning a story here would override their own recommendations. Its position can still be moved.'
                            : 'This band lists areas, not stories — pinning does not apply to it.'}
                        </p>
                      ) : (
                        <>
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
                                  aria-label="Find a story by headline"
                                  onChange={(e) => setQuery(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                      e.preventDefault()
                                      runSearch()
                                    }
                                  }}
                                  placeholder="Find a story by headline…"
                                  type="search"
                                  value={query}
                                />
                                <button className="fp__btn" onClick={runSearch} type="button">
                                  {searching ? 'Searching…' : 'Search'}
                                </button>
                              </div>
                            )}
                            {results.length > 0 && (
                              <ul className="fp__search-results">
                                {results.map((a) => (
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
                              <span className="fp__muted">(newest first — a guide to what readers will see, not an exact copy)</span>
                            </p>
                            {autoFillLoading === i ? (
                              <p className="fp__empty">Checking…</p>
                            ) : (
                              <ul className="fp__autofill-list">
                                {(autoFill[i] ?? []).length === 0 ? (
                                  <li className="fp__empty">
                                    <em>Nothing to show yet for this band.</em>
                                  </li>
                                ) : (
                                  (autoFill[i] ?? []).map((a) => (
                                    <li key={a.id}>
                                      <span>{a.title}</span>
                                      <span className="fp__muted">{when(a.publishedAt)}</span>
                                    </li>
                                  ))
                                )}
                              </ul>
                            )}
                            <button className="fp__btn" onClick={() => loadAutoFill(i)} type="button">
                              Refresh preview
                            </button>
                          </div>
                        </>
                      )}
                    </div>
                  )}
                </li>
              )
            })}
          </ol>

          {!readOnly && (
            <div className="fp__add-band">
              <select aria-label="Band to add" onChange={(e) => setAddChoice(e.target.value)} value={addChoice}>
                <option value="">Add a band…</option>
                {addOptions.map((opt) => (
                  <option key={opt.key} value={opt.key}>
                    {opt.label}
                  </option>
                ))}
                <option value={CUSTOM_OPTION}>Something else (advanced)…</option>
              </select>
              {addChoice === CUSTOM_OPTION && (
                <input
                  aria-label="Internal name (advanced)"
                  onChange={(e) => setCustomKey(e.target.value)}
                  placeholder="Internal name (advanced)"
                  type="text"
                  value={customKey}
                />
              )}
              <button className="fp__btn" disabled={!addChoice || (addChoice === CUSTOM_OPTION && !customKey.trim())} onClick={addBand} type="button">
                Add
              </button>
            </div>
          )}

          {!readOnly && (
            <div className="fp__row-actions fp__row-actions--main">
              <button className="fp__btn fp__btn--primary" disabled={pending} onClick={onSave} type="submit">
                {pending ? 'Saving…' : 'Save order'}
              </button>
            </div>
          )}
        </div>

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
    </div>
  )
}
