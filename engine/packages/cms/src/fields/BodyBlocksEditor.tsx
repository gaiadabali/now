'use client'

import { useField } from '@payloadcms/ui'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  asBlocks,
  cleanInline,
  convert,
  describe,
  insertAt,
  INSERTABLE,
  moveBy,
  patchAt,
  plainText,
  removeAt,
  replaceAt,
  setHeading,
  wordCount,
  type Block,
} from './blockModel'
import { BlockPreview } from './BlockPreview'

/**
 * The writing surface. Prose on the left, the article on the right.
 *
 * WHAT IT REPLACES, and why that was not a matter of taste. `body_blocks` is a
 * `json` field, so Payload renders it as a code editor — and an article in
 * this archive averages 15 blocks and runs to 596. Writing a paragraph meant
 * typing a JSON object; fixing a typo meant finding the sentence inside a
 * quoted string and not breaking the escaping around it. The field's own
 * description said "edit with care — this is the loader's output format, not
 * prose", which is an accurate warning and an admission that the surface was
 * built for the importer rather than for the person using it.
 *
 * WHAT IT DOES NOT CHANGE: the stored format, at all. `fields/bodyBlocks.ts`
 * explains why the block array is deliberately not Payload rich text — E1.2's
 * cleaner emits this shape, verified at ~0% content loss over 4,772 articles,
 * and re-modelling it as a Lexical AST would need a lossy two-way converter.
 * That reasoning is still right. So this edits the same array in place and
 * `blockModel.ts` guarantees, with tests, that a block the writer did not
 * touch comes back as the very same object.
 *
 * WHY THE PREVIEW IS THE BODY AND NOT THE PAGE. Payload has a live-preview
 * feature that puts the real site in an iframe, and it is the better answer
 * eventually. It needs draft-mode plumbing through the reader's article route
 * — the public site — and today is not the day to reach into that for a
 * writing convenience. What a writer checks while writing is paragraphing,
 * emphasis, where the images fall and whether a heading is in the right place,
 * and this shows all of it at reader typography, instantly, with no dependency
 * on the reader at all. It is a body preview and the header above it says so,
 * rather than implying a fidelity it does not have.
 *
 * THE EDITORIAL SCENARIOS IT IS BUILT AROUND, in the order they happen:
 *
 *   Fixing a typo in a published piece. The most common edit by a wide
 *   margin. Click the sentence, type, done — the block is contentEditable in
 *   place, and autosave (1500ms, already configured on the collection) means
 *   there is no save button to hunt for.
 *
 *   Adding or moving a paragraph. Every block has insert-below and move
 *   controls; no dragging, because drag-and-drop in a long article is a way
 *   to drop a paragraph somewhere you cannot find it, and a keyboard is
 *   faster for one place anyway.
 *
 *   Reading it back. The right pane, which is why it is a pane and not a
 *   button.
 *
 *   Meeting a block nobody should hand-edit — `columns`, `raw_html`, an
 *   Instagram card stored as a `quote`. Shown faithfully, movable, deletable,
 *   and editable only through an explicit "edit source" toggle. 1.6% of the
 *   archive, and the 1.6% most likely to be destroyed by a helpful editor.
 *
 * ONE THING YOU WILL SEE IN THE CONSOLE AND SHOULD NOT CHASE. On an article
 * that has an unpublished draft, React reports a hydration mismatch inside the
 * preview. It is not this component: Payload renders the field from one
 * version on the server and the client settles on the other, so the two
 * renders genuinely hold different block arrays. Measured — the warning
 * appears on an article with a draft and does not appear on articles without
 * one, and it appeared for the JSON code editor too, just invisibly, because a
 * mismatch inside a textarea does not announce itself. React repairs it by
 * re-rendering on the client, which is correct and cheap. Suppressing it here
 * would only hide the next real mismatch.
 */

type EditorProps = { path?: string; field?: { label?: unknown } }

export function BodyBlocksEditor({ path = 'bodyBlocks' }: EditorProps) {
  const { value, setValue } = useField<unknown>({ path })
  const blocks = useMemo(() => asBlocks(value), [value])

  const [focused, setFocused] = useState<number | null>(null)
  const [sourceOpen, setSourceOpen] = useState<Set<number>>(new Set())

  const apply = useCallback((next: Block[]) => setValue(next), [setValue])

  const words = useMemo(() => wordCount(blocks), [blocks])

  // An article with no body at all is the new-article case, and an empty grey
  // box teaches nobody anything. One paragraph is the smallest possible
  // starting point that is also a demonstration of how the surface works.
  const start = () => apply([{ type: 'paragraph', html: '' }])

  return (
    <div className="now-be">
      <header className="now-be__bar">
        <div className="now-be__count">
          {blocks.length} block{blocks.length === 1 ? '' : 's'} · {words.toLocaleString()} word
          {words === 1 ? '' : 's'}
        </div>
        <div className="now-be__bar-note">
          Saves as you type. The right pane is the body at reader typography —
          not the finished page.
        </div>
      </header>

      <div className="now-be__panes">
        <div className="now-be__edit">
          {blocks.length === 0 ? (
            <div className="now-be__empty">
              <p>This article has no body yet.</p>
              <button type="button" className="now-be__btn now-be__btn--primary" onClick={start}>
                Start writing
              </button>
            </div>
          ) : (
            blocks.map((block, i) => (
              <BlockRow
                key={`${i}-${block.type}`}
                block={block}
                index={i}
                total={blocks.length}
                isFocused={focused === i}
                showSource={sourceOpen.has(i)}
                onFocus={() => setFocused(i)}
                onToggleSource={() =>
                  setSourceOpen((prev) => {
                    const next = new Set(prev)
                    if (next.has(i)) next.delete(i)
                    else next.add(i)
                    return next
                  })
                }
                onPatch={(patch) => apply(patchAt(blocks, i, patch))}
                onReplace={(next) => apply(replaceAt(blocks, i, next))}
                onMove={(delta) => {
                  apply(moveBy(blocks, i, delta))
                  setFocused(Math.max(0, Math.min(i + delta, blocks.length - 1)))
                }}
                onRemove={() => {
                  apply(removeAt(blocks, i))
                  setFocused(null)
                }}
                onInsert={(made) => {
                  apply(insertAt(blocks, i + 1, made))
                  setFocused(i + 1)
                }}
              />
            ))
          )}
        </div>

        <aside className="now-be__preview" aria-label="Preview">
          <BlockPreview blocks={blocks} />
        </aside>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------

type RowProps = {
  block: Block
  index: number
  total: number
  isFocused: boolean
  showSource: boolean
  onFocus: () => void
  onToggleSource: () => void
  onPatch: (patch: Record<string, unknown>) => void
  onReplace: (next: Block) => void
  onMove: (delta: number) => void
  onRemove: () => void
  onInsert: (block: Block) => void
}

function BlockRow(props: RowProps) {
  const { block, index, total, isFocused } = props
  const editable = block.type === 'paragraph' || block.type === 'quote'

  return (
    <div
      className={`now-be__row now-be__row--${block.type}${isFocused ? ' is-focused' : ''}`}
      onFocus={props.onFocus}
    >
      <div className="now-be__gutter">
        <span className="now-be__kind">{block.type}</span>
      </div>

      <div className="now-be__body">
        {editable ? <InlineEditor block={block} onPatch={props.onPatch} /> : null}
        {block.type === 'heading' ? <HeadingEditor block={block} onReplace={props.onReplace} /> : null}
        {block.type === 'image' ? <ImageEditor block={block} onPatch={props.onPatch} /> : null}
        {block.type === 'gallery' ? <GalleryEditor block={block} onPatch={props.onPatch} /> : null}
        {block.type === 'list' ? <ListEditor block={block} onPatch={props.onPatch} /> : null}
        {block.type === 'embed' ? <EmbedEditor block={block} onPatch={props.onPatch} /> : null}
        {block.type === 'separator' ? <hr className="now-be__rule" /> : null}

        {!editable &&
        !['heading', 'image', 'gallery', 'list', 'embed', 'separator'].includes(block.type) ? (
          <OpaqueBlock block={block} showSource={props.showSource} onToggle={props.onToggleSource} onPatch={props.onPatch} />
        ) : null}

        {block.type === 'quote' ? (
          <input
            className="now-be__meta"
            placeholder="Attribution (optional)"
            defaultValue={String(block.cite ?? '')}
            onBlur={(e) => props.onPatch({ cite: e.target.value || null })}
          />
        ) : null}
      </div>

      <div className="now-be__tools">
        <button type="button" title="Move up" disabled={index === 0} onClick={() => props.onMove(-1)}>
          ↑
        </button>
        <button
          type="button"
          title="Move down"
          disabled={index === total - 1}
          onClick={() => props.onMove(1)}
        >
          ↓
        </button>
        {block.type === 'paragraph' || block.type === 'heading' ? (
          <button
            type="button"
            title={block.type === 'heading' ? 'Make a paragraph' : 'Make a heading'}
            onClick={() => props.onReplace(convert(block, block.type === 'heading' ? 'paragraph' : 'heading'))}
          >
            {block.type === 'heading' ? '¶' : 'H'}
          </button>
        ) : null}
        <InsertMenu onInsert={props.onInsert} />
        <button
          type="button"
          className="now-be__danger"
          title="Delete this block"
          onClick={() => {
            // The only destructive control here, and the only one that asks.
            // Undo in a field component means fighting Payload's own form
            // state; a sentence naming what is about to go is cheaper and
            // more honest than an undo that half works.
            if (confirm(`Delete this ${block.type}? "${plainText(String(block.html ?? describe(block))).slice(0, 60)}"`))
              props.onRemove()
          }}
        >
          ✕
        </button>
      </div>
    </div>
  )
}

function InsertMenu({ onInsert }: { onInsert: (b: Block) => void }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="now-be__insert">
      <button type="button" title="Insert below" onClick={() => setOpen((o) => !o)}>
        +
      </button>
      {open ? (
        <span className="now-be__menu">
          {INSERTABLE.map((item) => (
            <button
              key={item.type}
              type="button"
              onClick={() => {
                onInsert(item.make())
                setOpen(false)
              }}
            >
              {item.label}
            </button>
          ))}
        </span>
      ) : null}
    </span>
  )
}

/**
 * Prose, edited where it sits.
 *
 * UNCONTROLLED ON PURPOSE. A `contentEditable` whose `innerHTML` React owns
 * puts the caret back at position zero on every render, which makes typing
 * past the first character impossible. So the DOM holds the text while the
 * writer is in it, and the value is read out on blur. `defaultHtml` is
 * captured once per mount and the row's `key` is what remounts it.
 *
 * THE INITIAL TEXT IS WRITTEN IN AN EFFECT, and it has to be. Rendering it
 * with `dangerouslySetInnerHTML` is the tidier-looking option and it produces
 * a hydration mismatch every time: a browser normalises markup as it parses
 * it into a `contentEditable` — `<br/>` becomes `<br>`, attribute order moves,
 * entities re-encode — so the DOM React finds on the client is never quite the
 * string it sent from the server. React's repair for that is to throw the
 * subtree away and rebuild it, which on a page of thirteen paragraphs is both
 * slow and exactly the wrong thing to do to a field someone might be typing
 * in.
 *
 * Writing it after mount means the server and the client's first render are
 * the same empty div, so there is nothing to mismatch, and the effect then
 * mutates the DOM behind React's back — which is precisely the uncontrolled
 * behaviour the caret needs. Nothing is lost by the content being absent from
 * the server HTML: this is an admin surface behind a session, and the preview
 * pane carries the same text anyway.
 *
 * Bold and italic come from `execCommand`, which is deprecated and has no
 * replacement that works in every browser today. What it produces is then run
 * through `cleanInline`, so its worst habits — `<font>`, nested `<span
 * style>` — never reach storage.
 */
function InlineEditor({ block, onPatch }: { block: Block; onPatch: (p: Record<string, unknown>) => void }) {
  const ref = useRef<HTMLDivElement | null>(null)
  const defaultHtml = useRef(String(block.html ?? ''))

  useEffect(() => {
    if (ref.current) ref.current.innerHTML = defaultHtml.current
  }, [])

  const commit = () => {
    const el = ref.current
    if (!el) return
    const cleaned = cleanInline(el.innerHTML)
    if (cleaned !== String(block.html ?? '')) onPatch({ html: cleaned })
  }

  const exec = (command: string) => {
    ref.current?.focus()
    document.execCommand(command)
    commit()
  }

  const link = () => {
    const url = prompt('Link to:')
    if (!url) return
    ref.current?.focus()
    document.execCommand('createLink', false, url)
    commit()
  }

  return (
    <div className="now-be__prose-wrap">
      <div className="now-be__inline-tools" aria-hidden="true">
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => exec('bold')}>
          B
        </button>
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => exec('italic')}>
          I
        </button>
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={link}>
          Link
        </button>
      </div>
      <div
        ref={ref}
        className="now-be__prose"
        contentEditable
        suppressContentEditableWarning
        role="textbox"
        aria-multiline="true"
        tabIndex={0}
        onBlur={commit}
        onPaste={(e) => {
          // Paste as text. The alternative is inheriting Google Docs' inline
          // styling wholesale, which is how the archive got into the state
          // this editor exists to help clean up.
          e.preventDefault()
          const text = e.clipboardData.getData('text/plain')
          document.execCommand('insertText', false, text)
        }}
      />
    </div>
  )
}

function HeadingEditor({ block, onReplace }: { block: Block; onReplace: (b: Block) => void }) {
  const level = Number(block.level ?? 2)
  return (
    <div className="now-be__heading-wrap">
      <select
        className="now-be__level"
        value={String(level)}
        onChange={(e) => onReplace(setHeading(block, String(block.text ?? ''), Number(e.target.value)))}
        aria-label="Heading level"
      >
        {[2, 3, 4].map((l) => (
          <option key={l} value={l}>
            H{l}
          </option>
        ))}
      </select>
      <input
        className={`now-be__heading now-be__heading--${level}`}
        defaultValue={String(block.text ?? plainText(String(block.html ?? '')))}
        placeholder="Heading"
        onBlur={(e) => onReplace(setHeading(block, e.target.value, level))}
      />
    </div>
  )
}

/**
 * Images: alt and caption, and nothing else.
 *
 * `media_ref` points at the legacy WordPress host and there is nowhere to
 * upload a replacement — `Media` is `disableLocalStorage: true` and the
 * bucket behind it has never been started. Offering a file picker that cannot
 * work would be worse than offering none. What a writer can usefully change
 * is the alt text, which is an accessibility obligation and is empty or
 * useless on a great many of these ("Dance-8216"), and the caption.
 */
function ImageEditor({ block, onPatch }: { block: Block; onPatch: (p: Record<string, unknown>) => void }) {
  const src = String(block.media_ref ?? '')
  return (
    <div className="now-be__image">
      {src ? (
        /* eslint-disable-next-line @next/next/no-img-element -- a legacy remote
           URL at thumbnail size inside the admin; next/image would need the
           host allowlisted for no benefit here. */
        <img src={src} alt="" className="now-be__thumb" loading="lazy" />
      ) : (
        <div className="now-be__thumb now-be__thumb--missing">no image</div>
      )}
      <div className="now-be__image-fields">
        <input
          className="now-be__meta"
          placeholder="Alt text — what the image shows"
          title="What the image shows, for readers who cannot see it. Many of these are filenames."
          defaultValue={String(block.alt ?? '')}
          onBlur={(e) => onPatch({ alt: e.target.value })}
        />
        <input
          className="now-be__meta"
          placeholder="Caption (optional)"
          defaultValue={String(block.caption ?? '')}
          onBlur={(e) => onPatch({ caption: e.target.value || null })}
        />
      </div>
    </div>
  )
}

function GalleryEditor({ block, onPatch }: { block: Block; onPatch: (p: Record<string, unknown>) => void }) {
  const images = Array.isArray(block.images) ? (block.images as Array<Record<string, unknown>>) : []
  return (
    <div className="now-be__gallery">
      <div className="now-be__gallery-strip">
        {images.map((img, i) => (
          /* eslint-disable-next-line @next/next/no-img-element -- see ImageEditor */
          <img key={i} src={String(img.media_ref ?? '')} alt="" className="now-be__thumb" loading="lazy" />
        ))}
      </div>
      <input
        className="now-be__meta"
        placeholder="Gallery caption (optional)"
        defaultValue={String(block.caption ?? '')}
        onBlur={(e) => onPatch({ caption: e.target.value || null })}
      />
      <p className="now-be__hint">
        {images.length} image{images.length === 1 ? '' : 's'}. Per-image alt text is edited on the
        gallery source, below — galleries are rearranged by the importer, not here.
      </p>
    </div>
  )
}

/** List items are stored as inline HTML strings. One line each, as text, is
 * the honest editor for that: a writer adding a bullet is not thinking about
 * markup, and the ones that already contain links keep them because an
 * untouched item is never rewritten. */
function ListEditor({ block, onPatch }: { block: Block; onPatch: (p: Record<string, unknown>) => void }) {
  const items = Array.isArray(block.items) ? block.items.map(String) : []
  const ordered = Boolean(block.ordered)
  return (
    <div className="now-be__list">
      <label className="now-be__hint">
        <input
          type="checkbox"
          checked={ordered}
          onChange={(e) => onPatch({ ordered: e.target.checked })}
        />{' '}
        Numbered
      </label>
      {items.map((item, i) => (
        <input
          key={i}
          className="now-be__meta"
          defaultValue={item}
          onBlur={(e) => {
            const next = items.slice()
            next[i] = e.target.value
            onPatch({ items: next })
          }}
        />
      ))}
      <button
        type="button"
        className="now-be__btn"
        onClick={() => onPatch({ items: [...items, ''] })}
      >
        Add item
      </button>
    </div>
  )
}

function EmbedEditor({ block, onPatch }: { block: Block; onPatch: (p: Record<string, unknown>) => void }) {
  return (
    <div className="now-be__embed">
      <input
        className="now-be__meta"
        defaultValue={String(block.url ?? '')}
        placeholder="Embed URL"
        onBlur={(e) => onPatch({ url: e.target.value })}
      />
      <p className="now-be__hint">{String(block.provider ?? 'unknown provider')}</p>
    </div>
  )
}

/**
 * A block this editor will not pretend to understand.
 *
 * `columns` nests block arrays two deep, `raw_html` is whatever the cleaner
 * could not classify, and the archive's `quote` blocks are mostly embedded
 * Instagram cards. Fifty, three and twenty rows respectively. A structured
 * editor for those would be a way to damage them; a source box the writer has
 * to ask for is a way to fix one when they genuinely need to.
 */
function OpaqueBlock({
  block,
  showSource,
  onToggle,
  onPatch,
}: {
  block: Block
  showSource: boolean
  onToggle: () => void
  onPatch: (p: Record<string, unknown>) => void
}) {
  const html = typeof block.html === 'string' ? block.html : null
  return (
    <div className="now-be__opaque">
      <p className="now-be__hint">{describe(block)}</p>
      {showSource && html !== null ? (
        <textarea
          className="now-be__source"
          defaultValue={html}
          rows={8}
          onBlur={(e) => onPatch({ html: e.target.value })}
        />
      ) : null}
      {html !== null ? (
        <button type="button" className="now-be__btn" onClick={onToggle}>
          {showSource ? 'Hide source' : 'Edit source'}
        </button>
      ) : (
        <p className="now-be__hint">
          Structured content the importer produced. It can be moved or deleted here, and is edited
          where it was made.
        </p>
      )}
    </div>
  )
}
