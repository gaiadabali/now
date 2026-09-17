'use client'

import { useField } from '@payloadcms/ui'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  asBlocks,
  cleanInline,
  convert,
  countHardBreaks,
  describe,
  hasHardBreaks,
  insertAt,
  INSERTABLE,
  moveBy,
  patchAt,
  plainText,
  removeAt,
  replaceAt,
  setHeading,
  splitOnHardBreaks,
  wordCount,
  type Block,
} from './blockModel'
import { BlockPreview } from './BlockPreview'

/**
 * The writing surface: write on the left, read it back on the right.
 *
 * WHAT IT REPLACES, and why that was not a matter of taste. `body_blocks` is a
 * `json` field, so Payload renders it as a code editor — and an article in
 * this archive averages 15 blocks and runs to 596. Writing a paragraph meant
 * typing a JSON object; fixing a typo meant finding the sentence inside a
 * quoted string and not breaking the escaping around it. The field's own
 * description said "edit with care — this is the loader's output format, not
 * prose", which was accurate and was also an admission that the surface had
 * been built for the importer rather than for the person using it.
 *
 * WHAT IT DOES NOT CHANGE: the stored format, at all. `fields/bodyBlocks.ts`
 * explains why the block array is deliberately not Payload rich text — E1.2's
 * cleaner emits this shape, verified at ~0% content loss over 4,772 articles,
 * and re-modelling it as a Lexical AST would need a lossy two-way converter.
 * That reasoning is still right, so this edits the same array in place and
 * `blockModel.ts` guarantees with tests that a block nobody touched comes back
 * as the very same object.
 *
 * ONE TOOLBAR, ALWAYS VISIBLE, AND THAT IS A CORRECTION. The first version
 * hid its controls until hover: inline bold/italic per paragraph, block
 * controls per row, all of it invisible until the mouse happened to be in the
 * right place. It looked clean and it taught nobody anything — the owner's
 * first question on seeing the surface was what the two halves were for,
 * which is the answer to whether hover-revealed tools are discoverable. So
 * every action a writer needs now lives in one bar at the top of the column,
 * it stays on screen as they scroll, and it says what it does in words.
 *
 * The bar acts on the block with focus, and says which one that is. The
 * rejected alternative was a floating bubble over the selection, which is
 * prettier and is also the pattern that makes people hunt for a control they
 * saw once.
 *
 * WHY THE PREVIEW IS THE BODY AND NOT THE PAGE. Payload's own live preview
 * puts the real route in an iframe and is the better answer eventually; it
 * needs draft-mode plumbing through the public site, which is not a thing to
 * reach into for a writing convenience. What a writer checks while writing is
 * paragraphing, emphasis, where the images fall and whether a heading landed
 * right. All of that is here, instantly. The pane is labelled "How it will
 * read" rather than "Preview" for the same reason the bar is labelled at all.
 *
 * THE RUN-ON PARAGRAPH PROBLEM, found from a screenshot of this very surface.
 * The archive contains 11,042 paragraph blocks across 3,675 articles whose
 * text has newlines buried inside it, and 163 articles that are a single
 * block — a whole piece in one paragraph. HTML collapses those newlines, so
 * the reader gets one wall of text. The first version of this editor styled
 * its text `white-space: pre-wrap`, which drew them as separate paragraphs
 * and made the editor the only surface in the system telling a flattering
 * lie. That is gone. Instead the bar counts them and offers to split them,
 * and any block holding one says so on its own row.
 */

type EditorProps = { path?: string }

/**
 * The text the toolbar is acting on: which block, the live DOM node, and where
 * to write the result back to.
 *
 * Held in a ref rather than in state because the toolbar has to read the node
 * AFTER `execCommand` has mutated it, and a state round-trip would be a render
 * too late.
 *
 * `write` is a callback rather than "patch `html` on block `index`" because
 * the same editable serves two shapes: a paragraph, where the text IS
 * `block.html`, and one item of a list, where it is `block.items[j]`. Without
 * it, bold inside a bullet would either not work or would overwrite the whole
 * list with one item.
 */
type Active = { index: number; el: HTMLDivElement; write: (html: string) => void } | null

export function BodyBlocksEditor({ path = 'bodyBlocks' }: EditorProps) {
  const { value, setValue } = useField<unknown>({ path })
  const blocks = useMemo(() => asBlocks(value), [value])

  const [focused, setFocused] = useState<number | null>(null)
  const [sourceOpen, setSourceOpen] = useState<Set<number>>(new Set())
  const active = useRef<Active>(null)

  const apply = useCallback((next: Block[]) => setValue(next), [setValue])

  const words = useMemo(() => wordCount(blocks), [blocks])
  const runOns = useMemo(() => countHardBreaks(blocks), [blocks])

  const current = focused === null ? null : (blocks[focused] ?? null)

  /** Read the focused editable back out of the DOM and store it. Called after
   * every inline command, because `execCommand` edits the node and tells React
   * nothing. */
  const commitActive = useCallback(() => {
    const a = active.current
    if (!a) return
    a.write(cleanInline(a.el.innerHTML))
  }, [])

  const inline = useCallback(
    (command: string, arg?: string) => {
      const a = active.current
      if (!a) return
      a.el.focus()
      document.execCommand(command, false, arg)
      commitActive()
    },
    [commitActive],
  )

  const insert = useCallback(
    (block: Block) => {
      // Below the focused block, or at the end when nothing has focus — which
      // is what someone who has just opened the article and pressed a button
      // means by it.
      const at = focused === null ? blocks.length : focused + 1
      apply(insertAt(blocks, at, block))
      setFocused(at)
    },
    [apply, blocks, focused],
  )

  return (
    <div className="now-be">
      <Toolbar
        blocks={blocks}
        focused={focused}
        current={current}
        words={words}
        runOns={runOns}
        onInline={inline}
        onInsert={insert}
        onReplace={(next) => focused !== null && apply(replaceAt(blocks, focused, next))}
        onMove={(delta) => {
          if (focused === null) return
          apply(moveBy(blocks, focused, delta))
          setFocused(Math.max(0, Math.min(focused + delta, blocks.length - 1)))
        }}
        onDelete={() => {
          if (focused === null || !current) return
          const label = plainText(String(current.html ?? '')) || describe(current)
          if (!confirm(`Delete this ${current.type}?\n\n"${label.slice(0, 80)}"`)) return
          apply(removeAt(blocks, focused))
          setFocused(null)
        }}
        onSplitAll={() => {
          if (runOns === 0) return
          if (
            !confirm(
              `Split ${runOns} run-on block${runOns === 1 ? '' : 's'} into separate paragraphs?\n\n` +
                'These are paragraphs the importer never split. A reader sees them as one ' +
                'block of text today. Nothing else about the article changes.',
            )
          )
            return
          apply(blocks.flatMap((b) => splitOnHardBreaks(b)))
          setFocused(null)
        }}
      />

      <div className="now-be__panes">
        <section className="now-be__edit" aria-label="Write">
          <h4 className="now-be__pane-label">Write</h4>
          {blocks.length === 0 ? (
            <div className="now-be__empty">
              <p>This article has no body yet.</p>
              <button
                type="button"
                className="now-be__btn now-be__btn--primary"
                onClick={() => {
                  apply([{ type: 'paragraph', html: '' }])
                  setFocused(0)
                }}
              >
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
                onActivate={(el, write) => {
                  active.current = { index: i, el, write }
                  setFocused(i)
                }}
                onFocusRow={() => setFocused(i)}
                onCommit={commitActive}
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
                onSplit={() => {
                  const pieces = splitOnHardBreaks(block)
                  if (pieces.length < 2) return
                  apply([...blocks.slice(0, i), ...pieces, ...blocks.slice(i + 1)])
                  setFocused(i)
                }}
              />
            ))
          )}
        </section>

        <aside className="now-be__preview" aria-label="How it will read">
          <h4 className="now-be__pane-label">
            How it will read
            <span className="now-be__pane-note">the body only — no masthead or navigation</span>
          </h4>
          <BlockPreview blocks={blocks} />
        </aside>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// The toolbar
// ---------------------------------------------------------------------------

type ToolbarProps = {
  blocks: Block[]
  focused: number | null
  current: Block | null
  words: number
  runOns: number
  onInline: (command: string, arg?: string) => void
  onInsert: (block: Block) => void
  onReplace: (next: Block) => void
  onMove: (delta: number) => void
  onDelete: () => void
  onSplitAll: () => void
}

/** `onMouseDown` preventing default on every toolbar button is load-bearing,
 * not defensive. Without it, pressing the button blurs the text the writer had
 * selected, the selection collapses, and `execCommand` has nothing to act on —
 * bold silently does nothing, which is the single most common way a hand-built
 * toolbar is broken. */
const hold = (e: React.MouseEvent) => e.preventDefault()

function Toolbar(props: ToolbarProps) {
  const { current, focused, blocks, words, runOns } = props
  // `list` counts as prose for the Text group: its items are edited in the
  // same contentEditable, so bold and links work inside a bullet.
  const isProse =
    current?.type === 'paragraph' || current?.type === 'quote' || current?.type === 'list'
  const isHeading = current?.type === 'heading'
  const nothingFocused = focused === null || !current

  return (
    <div className="now-be__toolbar">
      <div className="now-be__tb-row">
        <span className="now-be__tb-group" role="group" aria-label="Text style">
          <span className="now-be__tb-label">Text</span>
          <button
            type="button"
            className="now-be__tb-btn now-be__tb-btn--b"
            title="Bold (Ctrl+B)"
            disabled={!isProse}
            onMouseDown={hold}
            onClick={() => props.onInline('bold')}
          >
            B
          </button>
          <button
            type="button"
            className="now-be__tb-btn now-be__tb-btn--i"
            title="Italic (Ctrl+I)"
            disabled={!isProse}
            onMouseDown={hold}
            onClick={() => props.onInline('italic')}
          >
            I
          </button>
          <button
            type="button"
            className="now-be__tb-btn"
            title="Link the selected words"
            disabled={!isProse}
            onMouseDown={hold}
            onClick={() => {
              const url = prompt('Link to:')
              if (url) props.onInline('createLink', url)
            }}
          >
            Link
          </button>
          <button
            type="button"
            className="now-be__tb-btn"
            title="Remove the link from the selected words"
            disabled={!isProse}
            onMouseDown={hold}
            onClick={() => props.onInline('unlink')}
          >
            Unlink
          </button>
        </span>

        <span className="now-be__tb-group" role="group" aria-label="This block">
          <span className="now-be__tb-label">This block</span>
          <button
            type="button"
            className="now-be__tb-btn"
            title="Turn this block into a paragraph"
            disabled={!isHeading}
            onMouseDown={hold}
            onClick={() => current && props.onReplace(convert(current, 'paragraph'))}
          >
            Paragraph
          </button>
          {[2, 3, 4].map((level) => (
            <button
              key={level}
              type="button"
              className={`now-be__tb-btn${isHeading && Number(current?.level) === level ? ' is-on' : ''}`}
              title={`Make this a level ${level} heading`}
              disabled={nothingFocused || !(isProse || isHeading)}
              onMouseDown={hold}
              onClick={() => {
                if (!current) return
                const asHeading = isHeading ? current : convert(current, 'heading')
                props.onReplace(setHeading(asHeading, String(asHeading.text ?? ''), level))
              }}
            >
              H{level}
            </button>
          ))}
          <button
            type="button"
            className="now-be__tb-btn"
            title="Move this block up"
            disabled={nothingFocused || focused === 0}
            onMouseDown={hold}
            onClick={() => props.onMove(-1)}
          >
            ↑
          </button>
          <button
            type="button"
            className="now-be__tb-btn"
            title="Move this block down"
            disabled={nothingFocused || focused === blocks.length - 1}
            onMouseDown={hold}
            onClick={() => props.onMove(1)}
          >
            ↓
          </button>
          <button
            type="button"
            className="now-be__tb-btn now-be__tb-btn--danger"
            title="Delete this block"
            disabled={nothingFocused}
            onMouseDown={hold}
            onClick={props.onDelete}
          >
            Delete
          </button>
        </span>

        <span className="now-be__tb-group" role="group" aria-label="Insert">
          <span className="now-be__tb-label">Insert</span>
          {INSERTABLE.map((item) => (
            <button
              key={item.type}
              type="button"
              className="now-be__tb-btn"
              title={
                focused === null
                  ? `Add a ${item.label.toLowerCase()} at the end`
                  : `Add a ${item.label.toLowerCase()} below the block you are in`
              }
              onMouseDown={hold}
              onClick={() => props.onInsert(item.make())}
            >
              {item.label}
            </button>
          ))}
        </span>
      </div>

      <div className="now-be__tb-row now-be__tb-row--status">
        <span className="now-be__tb-status">
          {blocks.length} block{blocks.length === 1 ? '' : 's'} · {words.toLocaleString()} word
          {words === 1 ? '' : 's'}
          {current ? (
            <>
              {' '}
              · in a <strong>{current.type}</strong>
            </>
          ) : (
            <span className="now-be__tb-hint"> · click a paragraph to start</span>
          )}
        </span>

        {runOns > 0 ? (
          <button
            type="button"
            className="now-be__tb-fix"
            onMouseDown={hold}
            onClick={props.onSplitAll}
            title="These paragraphs have line breaks buried inside them, which a reader never sees — they arrive as one block of text."
          >
            Fix {runOns} run-on paragraph{runOns === 1 ? '' : 's'}
          </button>
        ) : null}

        <span className="now-be__tb-saves">Saves as you type</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// One block
// ---------------------------------------------------------------------------

type RowProps = {
  block: Block
  index: number
  total: number
  isFocused: boolean
  showSource: boolean
  onActivate: (el: HTMLDivElement, write: (html: string) => void) => void
  onFocusRow: () => void
  onCommit: () => void
  onToggleSource: () => void
  onPatch: (patch: Record<string, unknown>) => void
  onReplace: (next: Block) => void
  onSplit: () => void
}

const STRUCTURED = ['heading', 'image', 'gallery', 'list', 'embed', 'separator']

function BlockRow(props: RowProps) {
  const { block, isFocused } = props
  const isProse = block.type === 'paragraph' || block.type === 'quote'
  const opaque = !isProse && !STRUCTURED.includes(block.type)

  return (
    <div
      className={`now-be__row now-be__row--${block.type}${isFocused ? ' is-focused' : ''}`}
      onFocus={props.onFocusRow}
    >
      <div className="now-be__gutter">
        <span className="now-be__kind">{block.type}</span>
        <span className="now-be__num">{props.index + 1}</span>
      </div>

      <div className="now-be__body">
        {isProse ? (
          <InlineEditor
            html={String(block.html ?? '')}
            onActivate={(el) => props.onActivate(el, (html) => props.onPatch({ html }))}
            onCommit={props.onCommit}
          />
        ) : null}
        {block.type === 'heading' ? <HeadingEditor block={block} onReplace={props.onReplace} /> : null}
        {block.type === 'image' ? <ImageEditor block={block} onPatch={props.onPatch} /> : null}
        {block.type === 'gallery' ? <GalleryEditor block={block} onPatch={props.onPatch} /> : null}
        {block.type === 'list' ? (
          <ListEditor
            block={block}
            onPatch={props.onPatch}
            onActivate={props.onActivate}
            onCommit={props.onCommit}
          />
        ) : null}
        {block.type === 'embed' ? <EmbedEditor block={block} onPatch={props.onPatch} /> : null}
        {block.type === 'separator' ? <hr className="now-be__rule" /> : null}
        {opaque ? (
          <OpaqueBlock
            block={block}
            showSource={props.showSource}
            onToggle={props.onToggleSource}
            onPatch={props.onPatch}
          />
        ) : null}

        {block.type === 'quote' ? (
          <input
            className="now-be__meta"
            placeholder="Attribution (optional)"
            defaultValue={String(block.cite ?? '')}
            onBlur={(e) => props.onPatch({ cite: e.target.value || null })}
          />
        ) : null}

        {/* Said on the row that has the problem, not only counted in the bar.
            A writer fixing one paragraph should be able to fix the one in front
            of them without reasoning about a number at the top of the page. */}
        {hasHardBreaks(block) ? (
          <p className="now-be__warn">
            This holds line breaks a reader never sees — it arrives as one block of text.{' '}
            <button type="button" className="now-be__link-btn" onMouseDown={hold} onClick={props.onSplit}>
              Split into paragraphs
            </button>
          </p>
        ) : null}
      </div>
    </div>
  )
}

/**
 * Prose, edited where it sits.
 *
 * UNCONTROLLED ON PURPOSE. A `contentEditable` whose `innerHTML` React owns
 * puts the caret back at position zero on every render, which makes typing
 * past the first character impossible. So the DOM holds the text while the
 * writer is in it, and the value is read out on blur and after every toolbar
 * command.
 *
 * THE INITIAL TEXT IS WRITTEN IN AN EFFECT, and it has to be. Rendering it
 * with `dangerouslySetInnerHTML` looks tidier and produces a hydration
 * mismatch every time: a browser normalises markup as it parses it into a
 * `contentEditable` — `<br/>` becomes `<br>`, attribute order moves, entities
 * re-encode — so the DOM React finds on the client is never quite the string
 * it sent from the server, and React's repair is to throw the subtree away.
 * Writing it after mount means both first renders are the same empty div.
 *
 * Bold and italic come from `execCommand`, which is deprecated and has no
 * replacement that works in every browser today. What it produces is run
 * through `cleanInline`, so its worst habits never reach storage.
 */
function InlineEditor({
  html,
  placeholder,
  onActivate,
  onCommit,
}: {
  html: string
  placeholder?: string
  onActivate: (el: HTMLDivElement) => void
  onCommit: () => void
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const defaultHtml = useRef(html)

  useEffect(() => {
    if (ref.current) ref.current.innerHTML = defaultHtml.current
  }, [])

  /**
   * RE-SYNC WHEN THE VALUE CHANGES UNDERNEATH US, which is a bug fix with a
   * screenshot behind it. Splitting a run-on paragraph turns one block into
   * five; React reuses this component for the first of them, the mount effect
   * above does not run again, and the DOM keeps the whole original text while
   * the preview correctly shows the five. The editor and the preview then
   * disagreed — the one thing this surface must never do.
   *
   * Guarded on focus. If the writer is typing in this element, the value
   * arriving from the parent is their own keystrokes coming back, and writing
   * it into the DOM would move the caret to the end of the paragraph on every
   * autosave. So the DOM wins while they are in it, and state wins when they
   * are not.
   */
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (el.innerHTML === html) return
    if (document.activeElement === el) return
    el.innerHTML = html
  }, [html])

  return (
    <div
      ref={ref}
      className="now-be__prose"
      data-placeholder={placeholder}
      contentEditable
      suppressContentEditableWarning
      role="textbox"
      aria-multiline="true"
      tabIndex={0}
      onFocus={() => ref.current && onActivate(ref.current)}
      onBlur={onCommit}
      onPaste={(e) => {
        // Paste as text. The alternative is inheriting Google Docs' inline
        // styling wholesale, which is how the archive got into the state this
        // editor exists to help clean up.
        e.preventDefault()
        const text = e.clipboardData.getData('text/plain')
        document.execCommand('insertText', false, text)
      }}
    />
  )
}

function HeadingEditor({ block, onReplace }: { block: Block; onReplace: (b: Block) => void }) {
  const level = Number(block.level ?? 2)
  return (
    <input
      className={`now-be__heading now-be__heading--${level}`}
      defaultValue={String(block.text ?? plainText(String(block.html ?? '')))}
      placeholder="Heading"
      onBlur={(e) => onReplace(setHeading(block, e.target.value, level))}
    />
  )
}

/**
 * Images: alt and caption, and nothing else.
 *
 * `media_ref` points at the legacy WordPress host and there is nowhere to
 * upload a replacement — `Media` is `disableLocalStorage: true` and the bucket
 * behind it has never been started. A file picker that cannot work would be
 * worse than none. What a writer can usefully change is the alt text, which is
 * an accessibility obligation and is empty or useless on a great many of these
 * ("Dance-8216"), and the caption.
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
        {images.length} image{images.length === 1 ? '' : 's'}, in the order the importer found them.
      </p>
    </div>
  )
}

/**
 * List items — edited as the text they are, not as the markup they are stored
 * as.
 *
 * These were plain `<input>`s bound to the stored string, which meant a writer
 * looking at a bulleted list saw
 * `A Three-Day stay at <strong><a href="https://…" target="_blank" rel="nore…`
 * in a single-line box. Honest, and the single most uncomfortable thing left
 * on the surface once the toolbar landed. Every item is now the same
 * `contentEditable` a paragraph uses, so the list reads as a list and the
 * toolbar's bold, italic and link work inside a bullet — which is what makes
 * one toolbar for everything true rather than nearly true.
 *
 * Items that already carry links keep them, because an untouched item is never
 * rewritten.
 */
function ListEditor({
  block,
  onPatch,
  onActivate,
  onCommit,
}: {
  block: Block
  onPatch: (p: Record<string, unknown>) => void
  onActivate: (el: HTMLDivElement, write: (html: string) => void) => void
  onCommit: () => void
}) {
  const items = Array.isArray(block.items) ? block.items.map(String) : []
  const ordered = Boolean(block.ordered)

  const writeItem = (at: number) => (html: string) => {
    const next = items.slice()
    next[at] = html
    onPatch({ items: next })
  }

  return (
    <div className="now-be__list">
      <label className="now-be__hint">
        <input type="checkbox" checked={ordered} onChange={(e) => onPatch({ ordered: e.target.checked })} />{' '}
        Numbered
      </label>

      <ol className={`now-be__items${ordered ? '' : ' now-be__items--bullets'}`}>
        {items.map((item, i) => (
          <li key={i}>
            <InlineEditor
              html={item}
              placeholder="List item"
              onActivate={(el) => onActivate(el, writeItem(i))}
              onCommit={onCommit}
            />
            <button
              type="button"
              className="now-be__item-x"
              title="Remove this item"
              onMouseDown={hold}
              onClick={() => onPatch({ items: items.filter((_, j) => j !== i) })}
            >
              ✕
            </button>
          </li>
        ))}
      </ol>

      <button type="button" className="now-be__btn" onClick={() => onPatch({ items: [...items, ''] })}>
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
 * could not classify. Fifty and three rows respectively across the archive. A
 * structured editor for those would be a way to damage them; a source box the
 * writer has to ask for is a way to fix one when they genuinely need to.
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
