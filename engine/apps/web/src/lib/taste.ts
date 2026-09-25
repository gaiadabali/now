/**
 * The pure arithmetic behind "For you"'s stated/revealed blend (WS1,
 * Edition 2, fourth pass, item 1) — pulled out of `recommend.ts` into its
 * own module with no `server-only` import, same reasoning as
 * `recommendSql.ts`/`competitorPolicy.ts`: this needs to be importable from
 * a plain `node --test` run (`recommend.ts` cannot be, its `server-only`
 * import throws outside Next's `react-server` condition), and the numbers
 * ARCHITECTURE §10 gives (α(0)=0, α(20)=0.5) deserve a direct unit test
 * rather than only being exercised indirectly through a live-DB path.
 */

// n_meaningful/(n_meaningful+20) — ARCHITECTURE §10's own constant.
export const ALPHA_HALF_LIFE = 20

/** `α = n_meaningful / (n_meaningful + 20)`. Never negative, never above 1
 * (n_meaningful is a count, so this needs no upper clamp in practice, but a
 * defensively-passed negative count still resolves to 0 rather than a
 * negative alpha). */
export function alphaFor(nMeaningful: number): number {
  if (nMeaningful <= 0) return 0
  return nMeaningful / (nMeaningful + ALPHA_HALF_LIFE)
}

export type TasteBlend = { vector: number[]; dominant: 'stated' | 'revealed' }

/**
 * `taste = α·revealed + (1−α)·stated_seed`. `null` only when NEITHER side
 * has anything — never invent taste. `dominant` says which side produced
 * more than half the blend, which is what the honest label (`labelFor`)
 * reads off.
 */
export function blendTaste(
  revealed: number[] | null,
  stated: number[] | null,
  nMeaningful: number,
): TasteBlend | null {
  if (revealed && stated) {
    const alpha = alphaFor(nMeaningful)
    return {
      vector: revealed.map((v, i) => alpha * v + (1 - alpha) * stated[i]),
      dominant: alpha < 0.5 ? 'stated' : 'revealed',
    }
  }
  if (stated) return { vector: stated, dominant: 'stated' }
  if (revealed) return { vector: revealed, dominant: 'revealed' }
  return null
}

/** §10/§17's honesty rule applied to the label: name whichever side of the
 * blend actually drove it, never both, never a guess. A `stated` dominance
 * with no resolvable labels (picks that matched no known term) still falls
 * back to the revealed-style label rather than rendering "Because you like
 * ". */
export function labelFor(dominant: 'stated' | 'revealed', statedLabels: readonly string[]): string {
  if (dominant === 'stated' && statedLabels.length > 0) {
    return `Because you like ${statedLabels.slice(0, 2).join(' and ')}`
  }
  return 'Because of what you read'
}
