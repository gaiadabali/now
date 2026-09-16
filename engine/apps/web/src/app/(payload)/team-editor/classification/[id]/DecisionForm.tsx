'use client'

import { useActionState, useState } from 'react'

import { decideReview, type DecisionResult } from './actions'

/**
 * The one interactive control on the report: deciding a single queued facet.
 *
 * Three outcomes, all first-class, because E2.8 made them so: accept the
 * classifier's proposal, correct it to another seeded term, or mark it
 * unclassifiable. The third is not a cop-out button — F49 seeded an `unknown`
 * sentinel term precisely so "we do not know" has somewhere real to point,
 * and forcing a reviewer to pick the least-wrong of three wrong types is how
 * a review queue starts producing worse data than the classifier it reviews.
 *
 * `useActionState` rather than a router refresh and a toast: the server action
 * returns the outcome, including the CMS's own error text when the collection
 * rejects a term (the F20 "restart to see new vocabulary" case is a real,
 * expected rejection with a precise message, and paraphrasing it into
 * "something went wrong" would cost the editor the one clue that matters).
 *
 * The client half of this component is only the disclosure — whether the
 * correction select is showing — and the pending flag. Everything that
 * decides anything is in `actions.ts`, on the server, re-checked there.
 */

export type ReviewOption = { slug: string; label: string; parentLabel: string | null }

export function DecisionForm({
  articleId,
  reviewId,
  proposedValue,
  options,
}: {
  articleId: number
  reviewId: number
  proposedValue: string
  options: ReviewOption[]
}) {
  const [state, formAction, pending] = useActionState<DecisionResult | null, FormData>(
    decideReview,
    null,
  )
  const [correcting, setCorrecting] = useState(false)

  return (
    <form action={formAction} className="classify__decide">
      <input type="hidden" name="articleId" value={articleId} />
      <input type="hidden" name="reviewId" value={reviewId} />

      {correcting ? (
        <>
          <label className="classify__visually-hidden" htmlFor={`final-${reviewId}`}>
            Correct to
          </label>
          <select
            id={`final-${reviewId}`}
            name="finalValue"
            defaultValue=""
            className="classify__select"
            required
          >
            <option value="" disabled>
              Correct to…
            </option>
            {options.map((o) => (
              <option key={o.slug} value={o.slug}>
                {o.label}
                {o.parentLabel ? ` — in ${o.parentLabel}` : ''}
                {o.slug === proposedValue ? ' (proposed)' : ''}
              </option>
            ))}
          </select>
          <button
            type="submit"
            name="decision"
            value="corrected"
            className="classify__btn classify__btn--primary"
            disabled={pending}
          >
            Save correction
          </button>
          <button
            type="button"
            className="classify__btn classify__btn--quiet"
            onClick={() => setCorrecting(false)}
            disabled={pending}
          >
            Cancel
          </button>
        </>
      ) : (
        <>
          <button
            type="submit"
            name="decision"
            value="accepted"
            className="classify__btn classify__btn--primary"
            disabled={pending}
          >
            Accept {proposedValue}
          </button>
          <button
            type="button"
            className="classify__btn"
            onClick={() => setCorrecting(true)}
            disabled={pending || options.length === 0}
            title={
              options.length === 0
                ? 'No seeded terms for this facet — the platform vocabulary is unreachable.'
                : undefined
            }
          >
            Correct…
          </button>
          <button
            type="submit"
            name="decision"
            value="unclassifiable"
            className="classify__btn classify__btn--quiet"
            disabled={pending}
          >
            Unclassifiable
          </button>
        </>
      )}

      {pending ? <span className="classify__decide-note">Saving…</span> : null}
      {state && !pending ? (
        <span
          className={`classify__decide-note${state.ok ? '' : ' classify__decide-note--error'}`}
          role="status"
        >
          {state.ok ? state.message : state.error}
        </span>
      ) : null}
    </form>
  )
}
