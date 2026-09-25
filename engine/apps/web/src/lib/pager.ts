/**
 * The pure arithmetic behind `team-editor/Pager.tsx` — split out so it can be
 * unit-tested without pulling in JSX (this project's test runner strips
 * TypeScript types only; it does not transform JSX, so a `.tsx` file cannot
 * be `import`ed from a `.test.ts`).
 */

const NEIGHBORS = 1

/** Which page numbers to show around the current one, `'sep'` standing in
 * for the gap an ellipsis marks. Mirrors `@payloadcms/ui`'s own `Pagination`
 * windowing algorithm exactly (`elements/Pagination/index.js`): the first
 * page, up to `NEIGHBORS` on each side of the current one, the last page,
 * and a separator wherever that leaves a gap of more than one. */
export function pageNodes(currentPage: number, totalPages: number): Array<number | 'sep'> {
  const pages = Array.from({ length: totalPages }, (_, i) => i + 1)
  let rangeStart = currentPage - 1 - NEIGHBORS
  if (rangeStart <= 0) rangeStart = 0
  const rangeEnd = currentPage - 1 + NEIGHBORS + 1
  const nodes: Array<number | 'sep'> = pages.slice(rangeStart, rangeEnd)
  if (currentPage - NEIGHBORS - 1 >= 2) nodes.unshift('sep')
  if (currentPage > NEIGHBORS + 1) nodes.unshift(1)
  if (currentPage + NEIGHBORS + 1 < totalPages) nodes.push('sep')
  if (rangeEnd < totalPages) nodes.push(totalPages)
  return nodes
}

/** "Showing 1–50 of 1,562" — the summary line Payload's own list pagination
 * pairs with its page numbers, so a paginated screen here still states the
 * total rather than only the current slice. */
export function pagerSummary(page: number, pageSize: number, total: number): string {
  if (total === 0) return 'Showing 0'
  const from = (page - 1) * pageSize + 1
  const to = Math.min(page * pageSize, total)
  return `Showing ${from.toLocaleString()}–${to.toLocaleString()} of ${total.toLocaleString()}`
}
