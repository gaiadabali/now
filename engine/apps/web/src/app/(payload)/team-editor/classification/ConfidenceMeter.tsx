import { CONFIDENCE_GATE } from '@/lib/classification'

/**
 * One confidence, drawn against the gate that decides what happens to it.
 *
 * The whole point of the component is the tick at {CONFIDENCE_GATE}. A bare
 * "0.40" tells a reviewer nothing: the number only means something relative to
 * ARCHITECTURE.md §6's threshold, and the threshold is why a review queue
 * exists at all. Drawing the bar without the gate would be drawing the
 * measurement and hiding the decision.
 *
 * No `<meter>` element, though it is semantically the closest fit: `<meter>`
 * paints its own green/amber/red from `low`/`high`/`optimum`, in a rendering
 * no browser lets you fully restyle and no two browsers agree on. This admin
 * has one palette and it is a warm paper ramp; a lime-green Chrome gauge in
 * the middle of it is exactly the "someone bolted on a dashboard" note the
 * skin in styles/admin.css exists to remove.
 *
 * `role="img"` with a full-sentence label rather than `progressbar`: this is a
 * static reading, not a value that changes, and a screen reader should get
 * "0.40, below the 0.85 review gate" in one utterance rather than a percentage
 * it has to relate to a threshold it was never told about.
 *
 * A plain server component. It has no state and no handler, so making it a
 * client component would ship React to the browser to draw two rectangles.
 */
export function ConfidenceMeter({
  confidence,
  label,
}: {
  /** `null` means the row stored no confidence — not the same as zero. */
  confidence: number | null
  label?: string
}) {
  if (confidence === null) {
    return <span className="classify__muted">no confidence recorded</span>
  }

  const clamped = Math.min(Math.max(confidence, 0), 1)
  const below = confidence < CONFIDENCE_GATE
  const reading = label ?? confidence.toFixed(2)

  return (
    <span className="classify__meter-wrap">
      <span
        className={`classify__meter${below ? ' classify__meter--below' : ''}`}
        role="img"
        aria-label={`${confidence.toFixed(2)} — ${below ? 'below' : 'clears'} the ${CONFIDENCE_GATE} review gate`}
      >
        <span className="classify__meter-fill" style={{ width: `${clamped * 100}%` }} />
        <span className="classify__meter-gate" style={{ left: `${CONFIDENCE_GATE * 100}%` }} />
      </span>
      <span className={`classify__meter-value${below ? ' classify__meter-value--below' : ''}`}>
        {reading}
      </span>
    </span>
  )
}
