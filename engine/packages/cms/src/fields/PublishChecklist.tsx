'use client'

import { useDocumentInfo, useFormFields } from '@payloadcms/ui'
import { useEffect, useState } from 'react'

import type { Block } from './blockModel'
import { wordCount } from './blockModel'

/**
 * "Ready to publish" — a sidebar panel for the writing screen, not a gate.
 *
 * DESIGN-SYSTEM.md §5's writing-screen section names four things this file
 * builds: the readiness checklist, a search-result preview, a social share
 * preview, and a word count/reading time. One component rather than four
 * registrations because they read the same six form fields and the same one
 * fetch, and a writer reads them as one question — "is this ready, and what
 * will it look like out there" — not four.
 *
 * INFORMS, DOES NOT BLOCK, beyond what Payload already requires (the
 * ticket's own words). Every row here is a fact stated plainly, never a
 * disabled Publish button — `primaryType`/`format` are the only fields
 * Payload itself already requires, and this does not duplicate that
 * enforcement, only surfaces it earlier and alongside the rest.
 *
 * TWO FACTS THIS FORM'S OWN STATE CANNOT ANSWER, and why a fetch is
 * unavoidable for them: the hero image's ALT TEXT (the form only holds
 * `heroMedia`'s id, never the related `media` document), and whether this
 * article carries the platform's `location` facet (`engine.entity_terms`,
 * which `packages/cms` must never touch — see
 * `apps/web/src/app/(payload)/api/article-checklist/[id]/route.ts`, the one
 * endpoint this file calls). Both come back together, once, after `heroMedia`
 * settles — not on every keystroke.
 */

const READING_WPM = 225

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return debounced
}

type ChecklistResponse = { heroAlt: string | null; heroUrl: string | null; hasArea: boolean | null }

export function PublishChecklist() {
  const { id, collectionSlug } = useDocumentInfo()

  const title = useFormFields(([fields]) => (fields.title?.value as string | undefined) ?? '')
  const dek = useFormFields(([fields]) => (fields.dek?.value as string | undefined) ?? '')
  const slug = useFormFields(([fields]) => (fields.slug?.value as string | undefined) ?? '')
  const primaryType = useFormFields(([fields]) => fields.primaryType?.value as string | undefined)
  const format = useFormFields(([fields]) => fields.format?.value as string | undefined)
  const heroMediaRaw = useFormFields(([fields]) => fields.heroMedia?.value)
  const bodyBlocksRaw = useFormFields(([fields]) => fields.bodyBlocks?.value)

  // The upload field's form value is the related doc's id, whether the
  // writer just picked it (a bare number) or Payload populated it for
  // display (an object carrying at least `id`) — both shapes are handled so
  // this does not silently stop working the day that populate behaviour
  // changes.
  const heroMediaId =
    typeof heroMediaRaw === 'number'
      ? heroMediaRaw
      : heroMediaRaw && typeof heroMediaRaw === 'object' && 'id' in heroMediaRaw
        ? Number((heroMediaRaw as { id: unknown }).id)
        : null

  const debouncedHeroId = useDebounced(heroMediaId, 400)
  const [checklist, setChecklist] = useState<ChecklistResponse>({ heroAlt: null, heroUrl: null, hasArea: null })
  const [checklistError, setChecklistError] = useState(false)

  useEffect(() => {
    if (collectionSlug !== 'articles' || !id) return
    const controller = new AbortController()
    const qs = debouncedHeroId ? `?heroMediaId=${debouncedHeroId}` : ''
    fetch(`/api/article-checklist/${id}${qs}`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: ChecklistResponse) => {
        setChecklist(data)
        setChecklistError(false)
      })
      .catch((err) => {
        if (err?.name !== 'AbortError') setChecklistError(true)
      })
    return () => controller.abort()
  }, [collectionSlug, id, debouncedHeroId])

  const words = wordCount(Array.isArray(bodyBlocksRaw) ? (bodyBlocksRaw as Block[]) : [])
  const minutes = words === 0 ? 0 : Math.max(1, Math.round(words / READING_WPM))

  const items: Array<{ label: string; ok: boolean | null; note: string }> = [
    {
      label: 'Headline',
      ok: title.trim().length > 0 && title.trim().length <= 70,
      note:
        title.trim().length === 0
          ? 'Not written yet.'
          : title.trim().length > 70
            ? `${title.trim().length} characters — most readers only see the first ~70 in a search result.`
            : `${title.trim().length} characters.`,
    },
    {
      label: 'Standfirst',
      ok: dek.trim().length > 0,
      note: dek.trim().length > 0 ? 'Written.' : 'Not written yet — the sentence that makes someone read on.',
    },
    {
      label: 'Hero image',
      ok: heroMediaId != null && (checklistError ? null : checklist.heroAlt != null),
      note:
        heroMediaId == null
          ? 'No picture chosen yet.'
          : checklistError
            ? "Couldn't check its alt text just now."
            : checklist.heroAlt != null
              ? 'Chosen, with alt text.'
              : 'Chosen, but its alt text is empty — add one on the Media item itself.',
    },
    {
      label: 'What it is about',
      ok: Boolean(primaryType),
      note: primaryType ? primaryType : 'Not chosen yet.',
    },
    {
      label: 'What kind of writing',
      ok: Boolean(format),
      note: format ? format : 'Not chosen yet.',
    },
    {
      label: 'Area',
      ok: checklistError ? null : checklist.hasArea,
      note: checklistError
        ? "Couldn't check just now."
        : checklist.hasArea == null
          ? id
            ? 'Not tagged with an area yet — the classifier or a reviewer sets this.'
            : 'Save the article first, then this can be checked.'
          : checklist.hasArea
            ? 'Tagged with an area.'
            : 'Not tagged with an area yet — the classifier or a reviewer sets this.',
    },
    {
      label: 'Web address',
      ok: slug.trim().length > 0,
      note: slug.trim().length > 0 ? `/${slug.trim()}` : 'Will be filled in from the headline.',
    },
  ]

  // NOT `typeof window !== 'undefined' ? window.location.origin : ''` — a
  // custom Payload field is still server-rendered once for hydration, where
  // `window` is undefined, and reading it inline would render the empty
  // string on the server and the real origin on the very first client pass,
  // which is exactly a hydration text mismatch. Starting at `''` and setting
  // it in an effect means the hydration render matches the server (`''`),
  // and the real origin appears in a normal post-hydration update instead.
  const [origin, setOrigin] = useState('')
  useEffect(() => setOrigin(window.location.origin), [])
  const previewTitle = title.trim() || 'Untitled story'
  const previewUrl = `${origin}/${slug.trim() || 'web-address'}`
  const previewDek = dek.trim() || 'No standfirst written yet — this space will look empty to a reader.'

  return (
    <div className="now-checklist">
      <p className="now-checklist__title">Ready to publish</p>
      <ul className="now-checklist__list">
        {items.map((item) => (
          <li className={`now-checklist__item now-checklist__item--${state(item.ok)}`} key={item.label}>
            <span className="now-checklist__mark" aria-hidden="true">
              {mark(item.ok)}
            </span>
            <span className="now-checklist__label">{item.label}</span>
            <span className="now-checklist__note">{item.note}</span>
          </li>
        ))}
      </ul>

      <div className="now-checklist__meta">
        <span>{words.toLocaleString()} words</span>
        <span>{minutes === 0 ? 'less than a minute' : `${minutes} min read`}</span>
      </div>

      <p className="now-checklist__title">How it looks in search</p>
      <div className="now-checklist__serp">
        <p className="now-checklist__serp-url">{previewUrl}</p>
        <p className="now-checklist__serp-title">{previewTitle}</p>
        <p className="now-checklist__serp-dek">{truncate(previewDek, 155)}</p>
      </div>

      <p className="now-checklist__title">How it looks shared</p>
      <div className="now-checklist__card">
        {checklist.heroUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- an admin
          // preview of an external, unmirrored legacy URL (Media.ts's own
          // note); next/image cannot optimise a host it does not know ahead
          // of time and this is not reader-facing.
          <img alt="" className="now-checklist__card-image" src={checklist.heroUrl} />
        ) : (
          <div className="now-checklist__card-image now-checklist__card-image--empty">No hero image</div>
        )}
        <div className="now-checklist__card-body">
          <p className="now-checklist__card-title">{previewTitle}</p>
          <p className="now-checklist__card-domain">{origin.replace(/^https?:\/\//, '')}</p>
        </div>
      </div>
    </div>
  )
}

function state(ok: boolean | null): 'ok' | 'warn' | 'unknown' {
  if (ok === null) return 'unknown'
  return ok ? 'ok' : 'warn'
}

function mark(ok: boolean | null): string {
  if (ok === null) return '…'
  return ok ? '✓' : '!'
}

function truncate(s: string, max: number): string {
  return s.length <= max ? s : `${s.slice(0, max - 1).trimEnd()}…`
}
