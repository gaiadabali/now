import Link from 'next/link'
import { notFound } from 'next/navigation'

import { requireReviewerAccess } from '@/lib/auth'
import { BULK_BATCH, CLUSTER_SAMPLE, getCluster } from '@/lib/review'

import { articleEditHref, classifyHref, REVIEW_ROOT } from '../../paths'
import { ConfidenceMeter } from '../../ConfidenceMeter'
import { BulkDecision, MemberDecision } from './Decisions'

/**
 * One cluster's workbench — the screen where the actual judgement happens.
 *
 * WHAT A REVIEWER HAS TO KNOW BEFORE THEY CAN DECIDE, in the order they need
 * it, which is the order this page is laid out in:
 *
 *   1. THE RULE. "164 articles whose WordPress category was News were
 *      classified type = stay, 41% confident." One sentence. Everything else
 *      on the page is evidence for or against it.
 *   2. WHY THE ENGINE THOUGHT SO, verbatim. This turned out to be the single
 *      most useful thing here and I did not expect it to be. Bali's largest
 *      `type` cluster explains itself as *"keyword cue instrument abstained
 *      (no cue cleared its margin threshold). Falling back to category prior
 *      (none available -> best-guess/unknown)"* — which is the classifier
 *      saying, in as many words, that it did not know. 158 of the 164 say
 *      that. No amount of reading the articles tells a reviewer what that one
 *      sentence does.
 *   3. WHAT IT CHANGES. Which column on the article the decision writes, or
 *      that it writes none — true of `subtype`, which is 2,941 of Bali's
 *      6,485 pending rows and has no article field at all. Someone should
 *      learn that before an afternoon, not after it.
 *   4. THE EXAMPLES, weakest first, each with its own decision buttons. Not a
 *      preview: a test. A reviewer who finds three that do not belong decides
 *      those three first, which takes them out of `pending` and therefore out
 *      of the bulk apply — no exclusion checkboxes, no client state that can
 *      drift from the server's idea of the set.
 *   5. THE BULK CONTROL, last, after all of it.
 *
 * WHY THE BULK CONTROL IS AT THE BOTTOM. It is the most powerful thing on the
 * page and the least reversible — `autoPopulateOnDecision` has no path back
 * to `pending`, deliberately. Putting it under the evidence is not decoration;
 * it is the only ordering where pressing it means the evidence was read.
 *
 * FORMERLY `classification/review/cluster/page.tsx`. S3.1 folded it into
 * `ClassificationView`'s dispatch — see `../../ClassificationView.tsx`. The
 * cluster key travels as query parameters (see `clusterHref` in `../../
 * paths.ts`), so — unlike the article report — this view needs nothing out of
 * Payload's raw path segments at all.
 */

const pct = (n: number | null): string => (n === null ? '—' : `${Math.round(n * 100)}%`)

export async function ClusterWorkbenchView({
  searchParams,
}: {
  searchParams: { facet?: string; legacy?: string; value?: string }
}) {
  await requireReviewerAccess()
  const { facet, legacy, value } = searchParams
  // `notFound()` bubbles to `team-editor/[[...segments]]/not-found.tsx` —
  // Payload's own not-found view, which is a correct place to land now that
  // this component renders inside Payload's catch-all rather than owning its
  // own route (S3.1). It was not always: before this ticket, this file WAS
  // that route, so the nearest boundary was the app's generic 404, not an
  // admin-chromed one.
  if (!facet || !value) notFound()

  const cluster = await getCluster({
    facetKey: facet,
    legacyCategory: legacy ?? '',
    proposedValue: value,
  })
  // Null means nothing in this pattern is pending any more — which is a
  // success, not a 404, and usually means a colleague just finished it.
  if (!cluster) {
    return (
      <>
        <p className="classify__crumb">
          <Link href={REVIEW_ROOT}>← Review desk</Link>
        </p>
        <h1>Nothing left here</h1>
        <p className="classify__sub">
          Every <code>{facet}</code> proposal for <strong>{legacy}</strong> ={' '}
          <code>{value}</code> has been decided.
        </p>
      </>
    )
  }

  const { key, pending, meanConfidence, reasonings, members, terms, targetField, proposalIsTerm } =
    cluster
  const options = terms.map((t) => ({ slug: t.slug, label: t.label, parentLabel: t.parentLabel }))

  return (
    <>
      <p className="classify__crumb">
        <Link href={REVIEW_ROOT}>← Review desk</Link>
      </p>

      <h1 className="classify__rule">
        <span className="classify__rule-n">{pending.toLocaleString()}</span> article
        {pending === 1 ? '' : 's'} filed under <strong>{key.legacyCategory}</strong> were classified{' '}
        <code>
          {key.facetKey} = {key.proposedValue}
        </code>
      </h1>

      <div className="classify__rule-meta">
        <ConfidenceMeter confidence={meanConfidence} label={pct(meanConfidence)} />
        <span className="classify__muted">
          average confidence · the gate is 85%
          {targetField ? (
            <>
              {' '}
              · writes <code>articles.{targetField}</code>
            </>
          ) : (
            <>
              {' '}
              ·{' '}
              <strong>
                no column on the article — recorded and sent to the engine, invisible in the edit
                form
              </strong>
            </>
          )}
        </span>
      </div>

      {!proposalIsTerm ? (
        <div className="classify__note classify__note--flag">
          <code>{key.proposedValue}</code> is not a term in the <code>{key.facetKey}</code>{' '}
          vocabulary at all — the classifier emitted a value the taxonomy has never contained. There
          is nothing here to accept. Correct the group to a real term, or mark it unclassifiable.
        </div>
      ) : null}

      <h2 className="classify__subhead">Why the engine said so</h2>
      <ul className="classify__reasons">
        {reasonings.map((r) => (
          <li className="classify__reason" key={r.text}>
            <span className="classify__reason-n">
              {r.count.toLocaleString()}×
            </span>
            <span className="classify__reasoning">{r.text}</span>
          </li>
        ))}
      </ul>

      <h2 className="classify__subhead">
        Check it against {Math.min(members.length, CLUSTER_SAMPLE)} of them
      </h2>
      <p className="classify__sub">
        The least confident first — these are the hardest cases in the group, so a rule that holds
        here holds throughout. Decide any that do not belong and they leave the group before the
        bulk apply below touches it.
      </p>

      <table>
        <thead>
          <tr>
            <th>Article</th>
            <th className="classify__num">Confidence</th>
            <th>Stored</th>
            <th>Decide this one</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.reviewId}>
              <td>
                <Link href={classifyHref(`/${m.articleId}`)}>{m.title || `Article ${m.articleId}`}</Link>
                {m.status !== 'published' ? (
                  <> <span className="classify__pill">{m.status}</span></>
                ) : null}
                {m.dek ? <div className="classify__dek">{m.dek}</div> : null}
                <div className="classify__muted">
                  <a href={articleEditHref(m.articleId)}>open in the editor</a>
                  {m.publishedAt ? <> · {m.publishedAt.slice(0, 10)}</> : null}
                </div>
              </td>
              <td className="classify__num">{pct(m.confidence)}</td>
              <td>
                {targetField === null ? (
                  <span className="classify__muted">n/a</span>
                ) : m.storedValue ? (
                  <code>{m.storedValue}</code>
                ) : (
                  <span className="classify__muted">not set</span>
                )}
              </td>
              <td>
                <MemberDecision
                  facetKey={key.facetKey}
                  legacyCategory={key.legacyCategory}
                  proposedValue={key.proposedValue}
                  reviewId={m.reviewId}
                  options={options}
                  proposalIsTerm={proposalIsTerm}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="classify__subhead">Decide the whole group</h2>
      <p className="classify__sub">
        A decision here is written with <code>source=&quot;editor&quot;</code> and the engine treats
        it as settled — it will not be overwritten by a re-run, and there is no path back to
        pending. Each one also writes the article and announces{' '}
        <code>classification.reviewed</code>, which is why it is not instant.
      </p>

      <BulkDecision
        facetKey={key.facetKey}
        legacyCategory={key.legacyCategory}
        proposedValue={key.proposedValue}
        pending={pending}
        batch={BULK_BATCH}
        proposalIsTerm={proposalIsTerm}
        options={options}
      />
    </>
  )
}
