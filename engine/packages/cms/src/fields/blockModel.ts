/**
 * The block array a writer is editing, as data rather than as a textarea.
 *
 * WHY THIS FILE IS SEPARATE FROM THE COMPONENT. Everything here is a pure
 * function over the stored array, so the one property that matters most can
 * actually be tested: **a block the writer did not touch comes back
 * byte-identical.** `articles.body_blocks` is E1.2's output, round-tripped
 * through `jsonb` with no schema coercion in either direction — that is the
 * guarantee `fields/bodyBlocks.ts` was built to make, and an editing surface
 * is the most likely thing to break it. Every mutation below copies the array
 * and replaces exactly one element by index; nothing walks the whole
 * structure, and nothing normalises a block it was not asked to change.
 *
 * WHAT THE ARCHIVE ACTUALLY CONTAINS, measured across one city's 4,429
 * articles (65,437 blocks), because it decides where the editing effort
 * goes. The city is not named here on purpose — ARCHITECTURE.md section 3.5
 * allows no site-name literal anywhere under `src/`, comments included, and
 * `lint:site-literals` enforces it without arguing about intent:
 *
 *     paragraph  43,016      embed        561
 *     image      11,608      list         443
 *     heading     4,200      columns       50
 *     gallery     3,172      quote         20
 *     separator   2,574      raw_html       3
 *
 * The first five are 98.7% of everything a writer will ever meet, and they
 * get real editing. The tail is 1.6% and is mostly not prose at all —
 * `columns` nests block arrays two deep, `raw_html` is the cleaner's own
 * admission of defeat, `quote` in this archive is overwhelmingly an embedded
 * Instagram card rather than a pull quote. Those are shown faithfully, can be
 * moved and deleted, and open a source editor only when the writer asks. A
 * half-working structured editor for fifty `columns` blocks would be a way to
 * damage them, not a way to edit them.
 */

/** A stored block. Deliberately not a discriminated union of every shape: the
 * validator in `bodyBlocks.ts` is loose on purpose so a new block type from
 * the cleaner does not hard-fail editor saves, and this has to be equally
 * forgiving or it would re-impose the same brittleness one layer up. */
export type Block = { type: string } & Record<string, unknown>

/** The types this editor can edit as content rather than as source. */
export const EDITABLE_TYPES = [
  'paragraph',
  'heading',
  'image',
  'gallery',
  'list',
  'quote',
  'embed',
  'separator',
] as const

/** Types a writer can insert. `columns`, `raw_html` and `gallery` are absent
 * deliberately: nothing in a writing session should create a structure whose
 * editor is a source box, and a gallery with no images is not a thing anyone
 * means to make. They can still be edited and moved where they already
 * exist. */
export const INSERTABLE: Array<{ type: string; label: string; make: () => Block }> = [
  { type: 'paragraph', label: 'Paragraph', make: () => ({ type: 'paragraph', html: '' }) },
  {
    type: 'heading',
    label: 'Heading',
    make: () => ({ type: 'heading', level: 2, text: '', html: '' }),
  },
  { type: 'list', label: 'List', make: () => ({ type: 'list', ordered: false, items: [''] }) },
  { type: 'quote', label: 'Quote', make: () => ({ type: 'quote', html: '', cite: null }) },
  { type: 'separator', label: 'Separator', make: () => ({ type: 'separator' }) },
]

export function asBlocks(value: unknown): Block[] {
  if (!Array.isArray(value)) return []
  return value.filter(
    (b): b is Block => typeof b === 'object' && b !== null && !Array.isArray(b) && 'type' in b,
  )
}

/**
 * Replace one block. The array is copied; every other element keeps its
 * identity, which is what makes "untouched blocks are unchanged" true by
 * construction rather than by care.
 */
export function replaceAt(blocks: Block[], index: number, next: Block): Block[] {
  if (index < 0 || index >= blocks.length) return blocks
  const out = blocks.slice()
  out[index] = next
  return out
}

/** Merge fields into one block, leaving keys this editor has no opinion about
 * exactly where they were — `media_ref`, `href`, `provider`, and anything the
 * cleaner adds later. */
export function patchAt(blocks: Block[], index: number, patch: Record<string, unknown>): Block[] {
  const current = blocks[index]
  if (!current) return blocks
  return replaceAt(blocks, index, { ...current, ...patch })
}

export function insertAt(blocks: Block[], index: number, block: Block): Block[] {
  const at = Math.max(0, Math.min(index, blocks.length))
  return [...blocks.slice(0, at), block, ...blocks.slice(at)]
}

export function removeAt(blocks: Block[], index: number): Block[] {
  if (index < 0 || index >= blocks.length) return blocks
  return [...blocks.slice(0, index), ...blocks.slice(index + 1)]
}

/** Move one block by `delta` places, clamped. Returns the same array when the
 * move would fall off either end, so the caller can treat "nothing happened"
 * as "no state change" rather than having to check bounds itself. */
export function moveBy(blocks: Block[], index: number, delta: number): Block[] {
  const to = index + delta
  if (index < 0 || index >= blocks.length || to < 0 || to >= blocks.length) return blocks
  const out = blocks.slice()
  const [moved] = out.splice(index, 1)
  out.splice(to, 0, moved)
  return out
}

/**
 * Tags to UNWRAP — keep the words, drop the element around them.
 *
 * A DENY-LIST, NOT AN ALLOW-LIST, AND THAT INVERSION IS THE WHOLE POINT.
 * This started as an allow-list of `B STRONG I EM A BR`, on the reasoning that
 * an editor should only produce markup it understands. Then a test of the real
 * surface deleted a photograph: `<img>` was not on the list, unwrapping a void
 * element removes it, and the paragraph came back without its image. Measured
 * afterwards across both cities, inside prose blocks:
 *
 *     STRONG  56,724     MARK  10,342     IMG   1,282
 *     A       22,706     SPAN   4,060     SUP   1,000
 *     BR      21,900     U      2,749     I       673
 *     EM      17,267     B      1,737     DIV     657     IFRAME 42
 *
 * An allow-list of six would have silently destroyed the img, sup, iframe,
 * small, time and sub content of any paragraph a writer happened to click
 * into. For an editing surface over a twenty-year archive the correct default
 * is PRESERVE THE UNKNOWN: an unrecognised tag is far likelier to be somebody's
 * content than somebody's mistake.
 *
 * So only presentational wrappers are named and everything else survives.
 * `MARK` and `SPAN` are here because in this archive they are almost entirely
 * `style="background-color:rgba(0,0,0,0)"` noise from the old editor; `DIV`
 * and `P` because a block-level element inside a paragraph is invalid anyway
 * and its children are the content.
 *
 * NOT A SECURITY BOUNDARY, and it must not be mistaken for one. The reader
 * sanitises on render — `apps/web/src/lib/html.ts` is the allowlist that
 * defends the page — and this editor cannot introduce a new tag in any case:
 * `execCommand` produces bold, italic and links, and paste is forced to plain
 * text. This is a tidiness rule for markup passing through, nothing more.
 */
const UNWRAP = new Set(['SPAN', 'MARK', 'DIV', 'P', 'FONT', 'CENTER', 'SECTION', 'BUTTON'])

/**
 * Attributes worth keeping, by tag.
 *
 * Everything else goes — `style`, `class`, `id`, every `on*` handler, and the
 * `wp-image-22536` classes the old editor sprinkled everywhere. What stays is
 * what carries meaning rather than appearance, which is why `alt` is on the
 * list and `width` is not: a stated width is a 2015 layout decision, and the
 * reader's own CSS is a better answer to it than the number is.
 */
const KEEP_ATTRS: Record<string, Set<string>> = {
  A: new Set(['href', 'title', 'target', 'rel']),
  IMG: new Set(['src', 'alt', 'title']),
  IFRAME: new Set(['src', 'title', 'allow', 'allowfullscreen']),
  TIME: new Set(['datetime']),
}

/** Exported for the tests: the policy is data, so it can be checked without a
 * DOM, while the walk below stays where a real parser is free. */
export function keepAttribute(tag: string, attr: string): boolean {
  return KEEP_ATTRS[tag.toUpperCase()]?.has(attr.toLowerCase()) ?? false
}

export function shouldUnwrap(tag: string): boolean {
  return UNWRAP.has(tag.toUpperCase())
}

/**
 * Links this editor is willing to leave in an `href`. Relative and fragment
 * links are fine; of the absolute schemes only http(s), mailto and tel belong
 * in prose. A `javascript:` href would be caught by the reader's sanitiser
 * too, but leaving it in the stored data means it is one sanitiser bug away
 * from mattering.
 */
export function isEditableHref(href: string): boolean {
  return /^(https?:|mailto:|tel:|[/#])/i.test(href.trim())
}

/**
 * Tidy markup that has passed through the editor, without destroying content.
 *
 * Runs in the browser and uses the DOM to parse, deliberately: a regex parser
 * for HTML is the wrong tool, and this only ever runs where a real parser is
 * free. The environment guard returns the input untouched rather than throwing
 * — losing a writer's paragraph to an environment check would be worse than
 * leaving a stray tag in it.
 */
export function cleanInline(html: string): string {
  if (typeof document === 'undefined') return html

  const host = document.createElement('div')
  host.innerHTML = html

  const walk = (node: Node): void => {
    // Snapshot the children: unwrapping mutates the live list underneath us.
    for (const child of Array.from(node.childNodes)) {
      if (child.nodeType === Node.TEXT_NODE) continue
      if (child.nodeType !== Node.ELEMENT_NODE) {
        // Comments and processing instructions. Not content.
        child.remove()
        continue
      }
      const el = child as HTMLElement
      walk(el)

      if (shouldUnwrap(el.tagName)) {
        // Unwrap, never delete. A `<span style>` around a sentence is noise;
        // the sentence is not.
        el.replaceWith(...Array.from(el.childNodes))
        continue
      }

      for (const attr of Array.from(el.attributes)) {
        if (!keepAttribute(el.tagName, attr.name)) el.removeAttribute(attr.name)
      }

      if (el.tagName === 'A') {
        const href = el.getAttribute('href') ?? ''
        if (!isEditableHref(href)) {
          // A link this editor will not vouch for loses its anchor and keeps
          // its words.
          el.replaceWith(...Array.from(el.childNodes))
          continue
        }
        el.setAttribute('rel', 'noreferrer noopener')
        if (/^https?:/i.test(href)) el.setAttribute('target', '_blank')
      }
    }
  }

  walk(host)
  return host.innerHTML.trim()
}

/**
 * Visible text of an inline-HTML string, for counting words and for showing a
 * collapsed block's first line.
 *
 * NO DOM, AND THAT IS THE WHOLE POINT. This used to branch — `textContent` in
 * the browser, a regex on the server — and the two do not agree: `textContent`
 * decodes `&amp;` and `&nbsp;`, the regex leaves them as literal text, and a
 * non-breaking space is a word boundary to one and not the other. Every
 * difference landed in the word count this component renders, which React then
 * reported as a hydration mismatch and repaired by throwing the editor's whole
 * subtree away and rebuilding it on the client.
 *
 * One algorithm, same answer everywhere. It handles the five XML entities plus
 * `&nbsp;` and numeric escapes, which is what twenty years of WordPress
 * actually left in this archive; anything more exotic survives as its literal
 * text, which is wrong by a word or two in a counter and wrong by nothing at
 * all in the stored data, since this function never writes anything back.
 */
export function plainText(html: string): string {
  return html
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&#(\d+);/g, (_, code: string) => String.fromCharCode(Number(code)))
    .replace(/&(amp|lt|gt|quot|apos);/g, (_, name: string) =>
      // `&amp;` last would double-decode `&amp;lt;` into `<`; doing them in one
      // pass over the original string is what stops that.
      ({ amp: '&', lt: '<', gt: '>', quot: '"', apos: "'" })[name] ?? _,
    )
    .replace(/\s+/g, ' ')
    .trim()
}

/**
 * Words of running prose: paragraphs, headings and list items.
 *
 * Captions, alt text and `cite` are excluded on purpose. A writer asking "how
 * long is this piece" means the body, and counting the alt text of eleven
 * gallery images into that number makes it useless for the only decision it
 * informs.
 */
export function wordCount(blocks: Block[]): number {
  let words = 0
  const add = (s: string) => {
    const t = plainText(s)
    if (t) words += t.split(/\s+/).length
  }
  for (const b of blocks) {
    if (b.type === 'paragraph' || b.type === 'quote') add(String(b.html ?? ''))
    else if (b.type === 'heading') add(String(b.text ?? b.html ?? ''))
    else if (b.type === 'list' && Array.isArray(b.items)) for (const i of b.items) add(String(i))
  }
  return words
}

/** A one-line summary for a block the editor shows but does not edit. */
export function describe(block: Block): string {
  switch (block.type) {
    case 'image':
      return String(block.alt || block.caption || 'Image')
    case 'gallery':
      return `Gallery — ${Array.isArray(block.images) ? block.images.length : 0} images`
    case 'embed':
      return String(block.provider || block.url || 'Embed')
    case 'columns':
      return `Columns — ${Array.isArray(block.columns) ? block.columns.length : 0} of them`
    case 'raw_html':
      return String(block.reason || 'Raw HTML the importer could not classify')
    case 'separator':
      return 'Section break'
    default:
      return block.type
  }
}

/**
 * Turn a heading into a paragraph or back.
 *
 * Both stored heading shapes are kept in step: the archive's headings carry
 * `text` AND `html`, and writing only one of them would leave the two
 * disagreeing — which nothing would catch, because every renderer in this
 * repository reads whichever it happens to prefer.
 */
export function convert(block: Block, to: 'paragraph' | 'heading'): Block {
  if (block.type === to) return block
  if (to === 'heading') {
    const text = plainText(String(block.html ?? ''))
    return { type: 'heading', level: 2, text, html: text }
  }
  const text = String(block.text ?? '') || plainText(String(block.html ?? ''))
  return { type: 'paragraph', html: text }
}

/** Heading edits have to write both fields, for the reason `convert` gives. */
export function setHeading(block: Block, text: string, level: number): Block {
  return { ...block, text, html: text, level }
}

/**
 * Does this block hold paragraph breaks that only LOOK like paragraphs?
 *
 * Found from a screenshot of the real editor, which is the best kind of bug
 * report: an article was a single `paragraph` block of 2,494 characters with
 * ten newlines inside it. The importer never split it. HTML collapses those
 * newlines to spaces, so the reader gets one run-on paragraph — and the
 * preview pane, correctly, showed exactly that while the editor's own
 * `white-space: pre-wrap` was drawing them as separate paragraphs. The
 * editor was the one lying.
 *
 * It is not rare. Measured across both cities: 11,042 paragraph blocks in
 * 3,675 articles carry a newline, and 163 articles are a single block like
 * that one. So this is a content-quality problem the archive arrived with,
 * and the editor's job is to make it visible and one click to fix rather
 * than to render it flatteringly.
 */
export function hasHardBreaks(block: Block): boolean {
  if (block.type !== 'paragraph' && block.type !== 'quote') return false
  return SPLIT_ON.test(String(block.html ?? ''))
}

/**
 * A newline, or two or more consecutive `<br>`.
 *
 * A SINGLE `<br>` is deliberately not a split point. In this archive it is
 * usually load-bearing — address lines, an opening-hours list, the name and
 * phone number of a restaurant — and breaking those into separate paragraphs
 * would space them apart and be a worse result than leaving them. A blank
 * line, or a doubled `<br>`, is what someone meant as a paragraph break.
 *
 * Global + `lastIndex` reset: a `RegExp` with `g` carries state between
 * `.test()` calls, which would make `hasHardBreaks` alternate true/false on
 * the same input. Cheaper to rebuild it per call than to remember that.
 */
const SPLIT_ON = /(?:\s*<br\s*\/?>\s*){2,}|\n+/i

/**
 * Split one run-on block into the paragraphs it was always meant to be.
 *
 * Returns the pieces, or `[block]` unchanged when there is nothing to split —
 * so a caller can apply it unconditionally and a no-op stays a no-op.
 *
 * Keys other than `html` are copied onto every piece. For a paragraph that is
 * only `type`, so it does not arise today; doing it anyway means a block that
 * later gains an attribute does not silently lose it here, and the wrong
 * behaviour (a duplicated attribute) is visible where the wrong behaviour of
 * dropping it would not be.
 */
export function splitOnHardBreaks(block: Block): Block[] {
  const html = String(block.html ?? '')
  const pieces = html
    .split(new RegExp(SPLIT_ON.source, 'gi'))
    .map((piece) => piece.trim())
    .filter(carriesSomething)

  if (pieces.length < 2) return [block]
  return pieces.map((piece) => ({ ...block, html: piece }))
}

/**
 * Elements that ARE the content, even with no text in them.
 *
 * This exists because of a deleted photograph. The filter above was once
 * `plainText(piece).length > 0`, meaning "drop the whitespace-only
 * fragments" — and a fragment holding nothing but `<img src=…>` has no text,
 * so splitting a paragraph silently threw the image away. Caught by driving
 * the real editor over a real article, not by reading the code, and it is the
 * second time the same instinct — "no words, no value" — cost content in this
 * file. The first was an allow-list of inline tags doing exactly the same
 * thing to the same image.
 *
 * So the rule is stated positively: a fragment survives if it has visible
 * text OR if it holds one of these. Anything else — a stray `<br>`, an empty
 * `<b></b>`, whitespace — is genuinely nothing and goes.
 */
const CARRIES_CONTENT = /<(img|iframe|video|audio|embed|object|svg|picture|source|table)\b/i

function carriesSomething(piece: string): boolean {
  if (piece.length === 0) return false
  return plainText(piece).length > 0 || CARRIES_CONTENT.test(piece)
}

/** How many blocks in this article are run-on — for the count the toolbar
 * shows, so the offer to fix them is proportionate to how many there are. */
export function countHardBreaks(blocks: Block[]): number {
  return blocks.filter(hasHardBreaks).length
}
