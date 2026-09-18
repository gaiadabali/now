/**
 * S3.2/S3.3/S4 — asserts the shape of the screen a writer opens.
 *
 * Layout is not usually worth a check. This is, for two reasons that have both
 * already happened here.
 *
 * The arrangement of the editing screen keeps being nobody's job. Fields get
 * appended to the end of the array as they are added, which is how "Legacy WP
 * ID" and a field whose description shouts DO NOT EDIT came to sit in the
 * middle of a writer's column, between the standfirst and the body. Nothing
 * failed, because nothing was looking.
 *
 * And F143: an admin config that is subtly wrong does not throw, it renders a
 * blank page behind a passing health check. Asserting against the real
 * SANITISED config catches a structural mistake here instead of in a browser
 * nobody opened.
 *
 * **Why a script and not a unit test.** `Articles.ts` imports `../access`, a
 * directory, which Payload's bundler resolves and plain Node ESM does not —
 * the package's two unit tests both cover leaf modules for that reason. This
 * runs through `payload run`, so it reads the config exactly as the admin
 * does, sanitisation and all, which is a stronger check than a hand-built one.
 *
 * What is deliberately NOT asserted: labels, descriptions and any wording.
 * Those should improve without a check to update. This pins structure and
 * invariants.
 *
 * Run with: npx payload run scripts/verify-article-admin.mjs
 */
import config from '../payload.config.ts'

const resolved = await config

const failures = []
const check = (ok, label, detail = '') => {
  console.log(`[verify] ${ok ? 'PASS' : 'FAIL'} — ${label}${detail ? ` :: ${detail}` : ''}`)
  if (!ok) failures.push(label)
}
const eq = (a, b, label) => check(JSON.stringify(a) === JSON.stringify(b), label, `got ${JSON.stringify(a)}`)

const articles = resolved.collections.find((c) => c.slug === 'articles')
if (!articles) {
  console.error('[verify] FAILED — no `articles` collection in the config')
  process.exit(1)
}

const top = articles.fields
const tabsField = top.find((f) => f.type === 'tabs')
const tabs = tabsField?.tabs ?? []
const names = (fields) => fields.map((f) => f.name).filter(Boolean)

/* -------------------------------------------------------------- grouping */

check(articles.admin?.group === 'Editorial', 'articles is in the Editorial sidebar group', String(articles.admin?.group))

// Every collection a writer sees should be grouped; an ungrouped one falls
// back to a flat entry above all the groups, which looks like a mistake.
const ungrouped = resolved.collections
  // Payload injects its own internal collections during sanitisation; they
  // are hidden from the sidebar anyway and are not ours to group.
  .filter(
    (c) =>
      !c.admin?.group &&
      !['payload-preferences', 'payload-locked-documents', 'payload-migrations', 'payload-kv', 'payload-jobs'].includes(
        c.slug,
      ),
  )
  .map((c) => c.slug)
check(ungrouped.length === 0, 'every collection declares a sidebar group', ungrouped.join(', '))

/* --------------------------------------------------------------- sidebar */

const sidebar = names(top.filter((f) => f.admin?.position === 'sidebar')).sort()
eq(sidebar, ['format', 'kind', 'primaryType', 'publishedAt'], 'the four non-writing decisions are in the sidebar')

// A required field on a tab nobody opens is a save that fails for a reason the
// writer cannot see. If either of these is ever moved into a tab, it has to
// stop being required first.
for (const name of ['primaryType', 'format']) {
  const f = top.find((x) => x.name === name)
  check(
    f?.admin?.position === 'sidebar' && f?.required === true,
    `${name} is required AND in the sidebar`,
    `position=${f?.admin?.position} required=${f?.required}`,
  )
}

/* ------------------------------------------------------------------ tabs */

check(tabs.length === 2, 'there are exactly two tabs', String(tabs.length))
eq(
  tabs.map((t) => t.label),
  ['Story', 'Old site'],
  'Story is the tab that opens first',
)

// THE check in this file. A named tab nests its children's data under that
// name, which would rename every one of these columns and need a migration.
// This change was meant to be presentation only.
const namedTabs = tabs.filter((t) => t.name).map((t) => t.name)
check(namedTabs.length === 0, 'every tab is UNNAMED, so no column moves', namedTabs.join(', '))

eq(
  names(tabs[0]?.fields ?? []),
  ['title', 'slug', 'dek', 'heroMedia', 'author', 'bodyBlocks'],
  'the Story tab holds what a writer touches, in reading order',
)
eq(
  names(tabs[1]?.fields ?? []),
  ['legacyPermalink', 'legacyWpId', 'seriesKey'],
  'the three import fields are on the Old site tab',
)

// The regression that prompted all of this.
const story = names(tabs[0]?.fields ?? [])
const leaked = ['legacyWpId', 'legacyPermalink', 'seriesKey'].filter((n) => story.includes(n))
check(leaked.length === 0, 'no import field is left in the writer default view', leaked.join(', '))

/* ------------------------------------------------- nothing was dropped */

// Sanitisation injects `_status` (from `versions.drafts`) and the two
// timestamps, so the expected set below includes them: this asserts against
// the config the admin actually renders, not the one this file declares.
const all = [...names(top.filter((f) => f.type !== 'tabs')), ...tabs.flatMap((t) => names(t.fields))]
eq(
  [...all].sort(),
  [
    '_status',
    'author',
    'bodyBlocks',
    'createdAt',
    'dek',
    'format',
    'heroMedia',
    'kind',
    'legacyPermalink',
    'legacyWpId',
    'primaryType',
    'publishedAt',
    'seriesKey',
    'slug',
    'title',
    'updatedAt',
  ],
  'every field still exists, exactly once, somewhere',
)
check(new Set(all).size === all.length, 'no field is declared twice')

/* --------------------------------------------------------- preview (S4) */

const preview = articles.admin?.preview
check(typeof preview === 'function', 'articles has a preview URL')
if (typeof preview === 'function') {
  const url = preview({ id: 123 }, { locale: undefined, req: {} })
  check(url === '/preview?collection=articles&id=123', 'preview points at the draft-mode route', String(url))
  // §3.5: one image serves every city, so an absolute URL here is either a
  // site literal (which `lint:site-literals` fails on) or the wrong city's
  // hostname baked into the other city's admin.
  check(typeof url === 'string' && url.startsWith('/'), 'the preview URL is relative', String(url))
  // The create screen renders before a row exists; `id=undefined` would 404
  // confusingly rather than simply not offering the button.
  check(preview({}, { locale: undefined, req: {} }) === null, 'no preview URL before the document has an id')
}

const lp = articles.admin?.livePreview
check(Boolean(lp), 'articles has a live preview config')
if (lp) {
  check(lp.url({ data: { id: 7 } }) === '/preview?collection=articles&id=7', 'live preview uses the same route')
  // Either side of the reader site's two real breakpoints (36rem, 62rem).
  eq(lp.breakpoints?.map((b) => b.width), [390, 820, 1440], 'live preview declares the real breakpoints')
}

if (failures.length > 0) {
  console.error(`\n[verify] FAILED — ${failures.length} check(s): ${failures.join('; ')}`)
  process.exit(1)
}
console.log('\n[verify] OK — the writer opens Story, the decisions are beside it, and preview is wired.')
process.exit(0)
