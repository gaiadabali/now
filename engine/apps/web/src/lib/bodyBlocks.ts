import 'server-only'

import { decodeEntities, isSafeHref, sanitizeHtml, stripTags } from '@/lib/html'

/**
 * `articles.body_blocks` → something a person can read.
 *
 * The field is a `jsonb` array of E1.2's cleaner output, and Payload's edit
 * form renders it with its JSON code editor — a syntax-highlighted
 * `[{"html": "<strong>Driving north from…", "type": "paragraph"}, …]`, 416
 * entries long on Bali's New Year listing. That one field is most of why the
 * edit page reads as machine output rather than as an article.
 *
 * The reader app already turns these into prose, but only partly:
 * `paragraphs()` in lib/payload.ts keeps `paragraph` blocks and discards
 * everything else, which is right for the reader (its pull-quote and
 * reading-time maths want plain running copy) and wrong here. Across the Bali
 * archive that filter drops 4,200 headings, 443 lists and 20 quotes — and a
 * heading is the single strongest classification signal a listing article
 * has. "DETOX AND RETOX" is the sentence that tells you the piece is `drink`.
 * So this is a second, fuller view model rather than a change to that one:
 * the reader's requirements have not changed, and widening `paragraphs()`
 * would alter the pull quote on every article to fix a report.
 *
 * Sanitising is reused wholesale from lib/html.ts — every `html` string here
 * goes through the same allowlist scanner the reader site uses, for the same
 * reason (twenty years of WordPress is exactly how stored XSS survives), and
 * the caller therefore receives vetted markup by construction.
 *
 * WHAT IS DELIBERATELY NOT RENDERED: the images. `media_ref` on a body block
 * is still the original `nowbali.co.id` / `nowjakarta.co.id` WordPress URL —
 * E1.3 rewrote the *hero* into Payload's media collection, not the 11,608
 * in-body ones. Rendering them would make the report hotlink the site it is
 * replacing, on a host next/image is not configured for, and a 416-block
 * listing would open hundreds of external connections per page view. The alt
 * text is kept and shown instead, which is the part carrying any
 * classification signal anyway.
 *
 * WHAT SURPRISED ME: every `quote` block in Bali's archive is an Instagram
 * embed's markup, not a pull quote — `<div style="padding:16px"><a
 * href="https://www.instagram.com/p/…">`. E1.2 classified it by container
 * tag. The sanitiser unwraps the divs and drops the styles, so it renders as
 * the link it really is; nothing special is done for it, and nothing should
 * be, because pretending it is a quotation would be the lie.
 */

export type ProseBlock =
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'paragraph'; html: string }
  | { kind: 'list'; ordered: boolean; items: string[] }
  | { kind: 'quote'; html: string; cite: string | null }
  | { kind: 'figure'; alt: string; caption: string | null }
  | { kind: 'gallery'; alts: string[] }
  /** `url` is `null` when the stored URL is not a scheme an `href` may use. */
  | { kind: 'embed'; provider: string | null; url: string | null; raw: string }
  | { kind: 'separator' }
  | { kind: 'raw'; html: string; reason: string | null }

export type BodyCensus = {
  blocks: ProseBlock[]
  /** Every block type present and how many, straight from the stored array. */
  counts: Array<{ type: string; count: number }>
  /** Words of running prose — paragraphs, headings and list items only. */
  words: number
  /** Blocks the stored array contained that this renderer has no case for. */
  unhandled: string[]
}

type RawBlock = Record<string, unknown>

const text = (value: unknown): string => stripTags(String(value ?? ''))

/**
 * One block to zero or more renderable pieces.
 *
 * `columns` is the only recursive case: its `columns` key is an array OF
 * arrays of blocks (WordPress's column layout), and E1.2 kept that nesting.
 * Flattening rather than reproducing the columns is deliberate — a two-column
 * venue list is a layout decision about the reader site, and what the report
 * needs is the 50 venue names inside it in reading order.
 */
function convert(block: RawBlock, unhandled: Set<string>): ProseBlock[] {
  const type = String(block.type ?? '')

  switch (type) {
    case 'heading': {
      const level = Number(block.level)
      return [
        {
          kind: 'heading',
          // Clamped, then offset at render time: a stored `h1` inside the body
          // must not compete with the report's own page title in the document
          // outline.
          level: Number.isFinite(level) ? Math.min(Math.max(level, 2), 6) : 3,
          text: decodeEntities(text(block.text ?? block.html)),
        },
      ]
    }

    case 'paragraph': {
      const html = sanitizeHtml(String(block.html ?? ''))
      return stripTags(html).length ? [{ kind: 'paragraph', html }] : []
    }

    case 'list': {
      const items = Array.isArray(block.items)
        ? block.items.map((i) => sanitizeHtml(String(i ?? ''))).filter((i) => stripTags(i).length > 0)
        : []
      return items.length ? [{ kind: 'list', ordered: Boolean(block.ordered), items }] : []
    }

    case 'quote': {
      const html = sanitizeHtml(String(block.html ?? ''))
      return stripTags(html).length
        ? [{ kind: 'quote', html, cite: block.cite ? decodeEntities(text(block.cite)) : null }]
        : []
    }

    case 'image': {
      const alt = decodeEntities(text(block.alt))
      const caption = block.caption ? decodeEntities(text(block.caption)) : null
      // An image with neither alt nor caption carries no signal and no
      // content; a row saying "image" 11,000 times would only add noise.
      return alt || caption ? [{ kind: 'figure', alt, caption }] : []
    }

    case 'gallery': {
      const images = Array.isArray(block.images) ? (block.images as RawBlock[]) : []
      const alts = images.map((i) => decodeEntities(text(i?.alt))).filter(Boolean)
      return [{ kind: 'gallery', alts }]
    }

    case 'embed': {
      // The one field in this file that becomes a link WITHOUT passing through
      // `sanitizeHtml` — `url` is a bare string, never markup, so the scanner
      // never sees it. React has not sanitised `href` since v16, so a stored
      // `javascript:` URL here would be a working click-to-execute XSS out of
      // the same twenty-year-old WordPress export the rest of this file is
      // careful about. Same allowlist, applied by hand because there is no
      // markup to scan: `isSafeHref` is exported from lib/html.ts precisely so
      // this is the same rule and not a second copy of it.
      const raw = String(block.url ?? '')
      return [
        {
          kind: 'embed',
          provider: block.provider ? String(block.provider) : null,
          url: raw && isSafeHref(raw) ? raw : null,
          // Kept regardless, and rendered as TEXT when it is not linkable. An
          // embed the report refuses to link is something a reviewer should be
          // able to see and copy, not something that silently disappears.
          raw,
        },
      ]
    }

    case 'separator':
      return [{ kind: 'separator' }]

    case 'columns': {
      const columns = Array.isArray(block.columns) ? (block.columns as RawBlock[][]) : []
      return columns.flat().flatMap((inner) => (inner ? convert(inner, unhandled) : []))
    }

    case 'raw_html': {
      const html = sanitizeHtml(String(block.html ?? ''))
      return stripTags(html).length
        ? [{ kind: 'raw', html, reason: block.reason ? String(block.reason) : null }]
        : []
    }

    default:
      // Named, not swallowed. E1.2's block vocabulary is versioned and can
      // grow; a report that silently omits a block type it has not met yet
      // would be quietly lying about the article's content.
      if (type) unhandled.add(type)
      return []
  }
}

export function readBody(bodyBlocks: unknown): BodyCensus {
  if (!Array.isArray(bodyBlocks)) {
    return { blocks: [], counts: [], words: 0, unhandled: [] }
  }

  const raw = bodyBlocks.filter((b): b is RawBlock => Boolean(b) && typeof b === 'object')
  const unhandled = new Set<string>()
  const blocks = raw.flatMap((b) => convert(b, unhandled))

  const tally = new Map<string, number>()
  for (const b of raw) {
    const type = String(b.type ?? 'unknown')
    tally.set(type, (tally.get(type) ?? 0) + 1)
  }

  const words = blocks.reduce((sum, b) => {
    const source =
      b.kind === 'paragraph' || b.kind === 'quote' || b.kind === 'raw'
        ? stripTags(b.html)
        : b.kind === 'heading'
          ? b.text
          : b.kind === 'list'
            ? b.items.map(stripTags).join(' ')
            : ''
    return sum + (source ? source.split(/\s+/).filter(Boolean).length : 0)
  }, 0)

  return {
    blocks,
    counts: [...tally.entries()].map(([type, count]) => ({ type, count })).sort((a, b) => b.count - a.count),
    words,
    unhandled: [...unhandled],
  }
}
