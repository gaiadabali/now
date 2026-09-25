/**
 * Which treatment a `department:<section>` band gets, given how many
 * department bands have already appeared on the page before it.
 *
 * Pulled out of `lib/frontPage.ts` into its own file with no `server-only`
 * import (that file has one, which requires `--conditions react-server` to
 * even load in a plain Node process — this needs to be unit-testable with
 * the project's ordinary `node --test` runner, no flag).
 *
 * The rule this exists for (DESIGN-SYSTEM §1/§2): `--ivory` is spent on
 * ONE department per page, and adjacent bands must not share a grid. Both
 * held automatically while there was only ever one `department:*` band in
 * the default order; they broke the moment a desk editor could place
 * several next to each other in `home_rails` — same "1 large + 3 side on
 * ivory" grid, repeated back to back, `--ivory` spent more than once.
 *
 * So only the FIRST department band on the page is `'ivory'`. Every one
 * after it cycles through two more treatments, both built from grids that
 * already exist elsewhere in the system rather than a new one invented for
 * this: `'mirror'` is `.grid--dept` itself with the lead and the side list
 * swapped left-for-right, on `--paper`; `'quad'` is The Edit's own 4-up
 * grid (`.grid--edit`), also on `--paper`, with the department's lead and
 * side items folded into one row of equals rather than a lead-plus-list.
 *
 * Cycling by the running count (not reset by a gap) rather than only by
 * adjacency: two department bands with a `guides` band between them are
 * still both real department bands on the same page, and cycling the
 * count regardless of what sits between them is what guarantees two
 * ADJACENT ones always land on different indices (consecutive integers are
 * never equal mod 3) without having to special-case "is the previous band
 * also a department band".
 */
export type DepartmentVariant = 'ivory' | 'mirror' | 'quad'

/** Never revisited past index 0 — `--ivory` is a per-PAGE budget, not a
 *  per-run one, so a fourth or fifth department band cycles between
 *  `mirror`/`quad` rather than wrapping back to the one tone the whole
 *  rule exists to spend exactly once. */
const REPEATING: DepartmentVariant[] = ['mirror', 'quad']

/** `index` is 0 for the first department band on the page, 1 for the
 *  second, and so on — not reset by position, section, or a gap. */
export function departmentVariant(index: number): DepartmentVariant {
  if (index <= 0) return 'ivory'
  return REPEATING[(index - 1) % REPEATING.length]
}
