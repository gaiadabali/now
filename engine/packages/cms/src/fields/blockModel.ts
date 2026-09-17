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
 * Inline markup the editor is willing to produce.
 *
 * Note what this is NOT: a security boundary. The archive already contains
 * `<mark style>`, `<span style>` and worse from twenty years of WordPress,
 * and the reader sanitises on render — `apps/web/src/lib/html.ts` is the
 * allowlist that actually defends the page. This is a tidiness rule for text
 * this editor itself creates, so a paste from Word does not quietly add a
 * decade more of `<font>` tags to a file we are trying to clean up.
 */
const ALLOWED_INLINE = new Set(['B', 'STRONG', 'I', 'EM', 'A', 'BR'])

/**
 * Reduce pasted or contentEditable-produced markup to the inline tags above.
 *
 * Runs in the browser and uses the DOM to parse, deliberately: a regex parser
 * for HTML is the wrong tool and this code already only ever runs where a
 * real parser is free. Callers must therefore only invoke it client-side; the
 * guard returns the input untouched rather than throwing, because losing a
 * writer's paragraph to an environment check would be worse than leaving one
 * stray tag in it.
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
        child.remove()
        continue
      }
      const el = child as HTMLElement
      walk(el)

      if (!ALLOWED_INLINE.has(el.tagName)) {
        // Unwrap rather than delete. A `<span style>` around a sentence is
        // noise; the sentence is not, and deleting the element would take the
        // writer's words with it.
        el.replaceWith(...Array.from(el.childNodes))
        continue
      }
      // Strip every attribute but the one that carries meaning.
      for (const attr of Array.from(el.attributes)) {
        if (!(el.tagName === 'A' && attr.name === 'href')) el.removeAttribute(attr.name)
      }
      if (el.tagName === 'A') {
        const href = el.getAttribute('href') ?? ''
        // Relative and fragment links are fine; of the absolute schemes only
        // http(s) and mailto belong in prose. A `javascript:` href reaching
        // the reader would be sanitised there too, but leaving it in the
        // stored data means it is one sanitiser bug away from mattering.
        const safe = /^(https?:|mailto:|[/#])/i.test(href)
        if (!safe) el.replaceWith(...Array.from(el.childNodes))
        else {
          el.setAttribute('rel', 'noreferrer noopener')
          if (/^https?:/i.test(href)) el.setAttribute('target', '_blank')
        }
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
