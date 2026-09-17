'use client'

import { useActionState, useState } from 'react'

import { decideCluster, decideOne, type BulkResult, type SingleResult } from './actions'

/**
 * The two controls on the workbench: decide the whole pattern, or decide one
 * article out of it.
 *
 * Both are the same three outcomes, because E2.8 made all three first-class
 * and the third is the one that matters most here. `unclassifiable` is not a
 * cop-out: F49 seeded an `unknown` term precisely so "we do not know" has
 * somewhere real to point, and Bali's largest `type` cluster is 158 articles
 * whose own reasoning reads *"keyword cue instrument abstained… falling back
 * to best-guess"*. Accepting those would be recording a coin-flip as a human
 * decision, with `source='editor'` on it, which §8.A then spends on a
 * commercial guarantee. Marking them unclassifiable is the honest answer and
 * it needs to be exactly as easy to reach as accepting.
 *
 * `useActionState` rather than a refresh-and-toast: the server returns the
 * real counts and, on failure, the CMS's own rejection text. Both are things
 * a reviewer needs verbatim — "80 decided, 20 refused — 'unresolved' is not a
 * seeded 'subtype' term" is actionable; "something went wrong" is not.
 */

export type TermOption = { slug: string; label: string; parentLabel: string | null }

function TermSelect({
  id,
  options,
  proposedValue,
}: {
  id: string
  options: TermOption[]
  proposedValue: string
}) {
  return (
    <>
      <label className="classify__visually-hidden" htmlFor={id}>
        Correct to
      </label>
      <select id={id} name="finalValue" defaultValue="" className="classify__select" required>
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
    </>
  )
}

/** Hidden inputs carrying the cluster key. The server re-derives which rows
 * that key matches; these three strings are the entire trust surface. */
function ClusterKeyFields({
  facetKey,
  legacyCategory,
  proposedValue,
}: {
  facetKey: string
  legacyCategory: string
  proposedValue: string
}) {
  return (
    <>
      <input type="hidden" name="facet" value={facetKey} />
      <input type="hidden" name="legacy" value={legacyCategory} />
      <input type="hidden" name="value" value={proposedValue} />
    </>
  )
}

export function BulkDecision({
  facetKey,
  legacyCategory,
  proposedValue,
  pending,
  batch,
  proposalIsTerm,
  options,
}: {
  facetKey: string
  legacyCategory: string
  proposedValue: string
  pending: number
  batch: number
  proposalIsTerm: boolean
  options: TermOption[]
}) {
  const [state, formAction, busy] = useActionState<BulkResult | null, FormData>(decideCluster, null)
  const [correcting, setCorrecting] = useState(false)

  const thisPass = Math.min(pending, batch)
  const more = pending > batch

  return (
    <form action={formAction} className="classify__bulk">
      <ClusterKeyFields
        facetKey={facetKey}
        legacyCategory={legacyCategory}
        proposedValue={proposedValue}
      />

      <p className="classify__bulk-scope">
        Applies to <strong>{thisPass.toLocaleString()}</strong>
        {more ? (
          <>
            {' '}
            of {pending.toLocaleString()} — the rest stay pending and the button comes back
          </>
        ) : (
          <> article{thisPass === 1 ? '' : 's'}</>
        )}
        .
      </p>

      {correcting ? (
        <div className="classify__bulk-row">
          <TermSelect id="bulk-final" options={options} proposedValue={proposedValue} />
          <button
            type="submit"
            name="decision"
            value="corrected"
            className="classify__btn classify__btn--primary"
            disabled={busy}
          >
            Correct all {thisPass.toLocaleString()}
          </button>
          <button
            type="button"
            className="classify__btn classify__btn--quiet"
            onClick={() => setCorrecting(false)}
            disabled={busy}
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="classify__bulk-row">
          <button
            type="submit"
            name="decision"
            value="accepted"
            className="classify__btn classify__btn--primary"
            disabled={busy || !proposalIsTerm}
            title={
              proposalIsTerm
                ? undefined
                : `"${proposedValue}" is not a term in this facet's vocabulary, so there is nothing to accept.`
            }
          >
            Accept {proposedValue}
          </button>
          <button
            type="button"
            className="classify__btn"
            onClick={() => setCorrecting(true)}
            disabled={busy || options.length === 0}
          >
            Correct all to…
          </button>
          <button
            type="submit"
            name="decision"
            value="unclassifiable"
            className="classify__btn classify__btn--quiet"
            disabled={busy}
          >
            None of these — unclassifiable
          </button>
        </div>
      )}

      {busy ? (
        <p className="classify__decide-note" role="status">
          Deciding {thisPass.toLocaleString()} — each one writes the article and tells the engine,
          so this takes a moment.
        </p>
      ) : null}

      {state && !busy ? (
        <p
          className={`classify__decide-note${state.ok ? '' : ' classify__decide-note--error'}`}
          role="status"
        >
          {state.ok ? state.note : state.error}
          {state.ok && state.remaining > 0 ? ' Press again for the next batch.' : null}
        </p>
      ) : null}
    </form>
  )
}

export function MemberDecision({
  facetKey,
  legacyCategory,
  proposedValue,
  reviewId,
  options,
  proposalIsTerm,
}: {
  facetKey: string
  legacyCategory: string
  proposedValue: string
  reviewId: number
  options: TermOption[]
  proposalIsTerm: boolean
}) {
  const [state, formAction, busy] = useActionState<SingleResult | null, FormData>(decideOne, null)
  const [correcting, setCorrecting] = useState(false)

  // Once decided, the row is gone from the cluster on the next load; saying so
  // beats leaving live buttons on a row that is no longer pending.
  if (state?.ok) {
    return (
      <span className="classify__decide-note" role="status">
        {state.message}
      </span>
    )
  }

  return (
    <form action={formAction} className="classify__decide classify__decide--inline">
      <ClusterKeyFields
        facetKey={facetKey}
        legacyCategory={legacyCategory}
        proposedValue={proposedValue}
      />
      <input type="hidden" name="reviewId" value={reviewId} />

      {correcting ? (
        <>
          <TermSelect id={`final-${reviewId}`} options={options} proposedValue={proposedValue} />
          <button
            type="submit"
            name="decision"
            value="corrected"
            className="classify__btn classify__btn--primary"
            disabled={busy}
          >
            Save
          </button>
          <button
            type="button"
            className="classify__btn classify__btn--quiet"
            onClick={() => setCorrecting(false)}
            disabled={busy}
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
            className="classify__btn"
            disabled={busy || !proposalIsTerm}
          >
            Accept
          </button>
          <button
            type="button"
            className="classify__btn"
            onClick={() => setCorrecting(true)}
            disabled={busy || options.length === 0}
          >
            Correct…
          </button>
          <button
            type="submit"
            name="decision"
            value="unclassifiable"
            className="classify__btn classify__btn--quiet"
            disabled={busy}
          >
            Neither
          </button>
        </>
      )}

      {state && !state.ok && !busy ? (
        <span className="classify__decide-note classify__decide-note--error" role="status">
          {state.error}
        </span>
      ) : null}
    </form>
  )
}
