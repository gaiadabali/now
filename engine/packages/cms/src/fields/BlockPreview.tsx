'use client'

import { describe, type Block } from './blockModel'

/**
 * The right pane: the body as prose, updating as it is typed.
 *
 * WHAT IT IS AND IS NOT. This is the article's *body* at reader typography —
 * serif, measured line length, images in the flow, headings at their stored
 * level. It is not the finished page: no masthead, no chips, no related
 * stories. The bar above it says so in as many words, because a preview that
 * implies more fidelity than it has is worse than no preview — it is the one
 * that gets trusted right up until something looks different in production.
 *
 * The honest alternative is Payload's own live preview, which puts the real
 * reader route in an iframe. That needs draft-mode plumbing through the public
 * site and is the right thing to build once. What a writer checks *while
 * writing* is paragraphing, emphasis, where the images fall and whether a
 * heading landed in the right place, and all of that is here, instantly.
 *
 * ON `dangerouslySetInnerHTML`: the alternative is React escaping the
 * archive's own inline markup and printing `<strong>` at the writer, which is
 * very nearly the complaint that produced this whole surface. What reaches it
 * is either markup the importer already stored — which the reader sanitises on
 * render, `apps/web/src/lib/html.ts` being the allowlist that actually defends
 * the page — or markup this editor just produced through `cleanInline`. The
 * attribute's name is louder than the risk, and the risk is not zero; it is
 * the same risk the reader and the classification report already carry, taken
 * knowingly and in one more place.
 */
export function BlockPreview({ blocks }: { blocks: Block[] }) {
  if (blocks.length === 0) {
    return <p className="now-bp__empty">Nothing to preview yet.</p>
  }

  return (
    <article className="now-bp">
      {blocks.map((block, i) => {
        switch (block.type) {
          case 'heading': {
            const level = Math.min(Math.max(Number(block.level ?? 2), 2), 4)
            const Tag = `h${level}` as 'h2' | 'h3' | 'h4'
            return <Tag key={i}>{String(block.text ?? '')}</Tag>
          }

          case 'paragraph':
            return (
              <p key={i} dangerouslySetInnerHTML={{ __html: String(block.html ?? '') }} />
            )

          case 'quote':
            return (
              <blockquote key={i}>
                <div dangerouslySetInnerHTML={{ __html: String(block.html ?? '') }} />
                {block.cite ? <cite>{String(block.cite)}</cite> : null}
              </blockquote>
            )

          case 'list': {
            const items = Array.isArray(block.items) ? block.items.map(String) : []
            const Tag = block.ordered ? 'ol' : 'ul'
            return (
              <Tag key={i}>
                {items.map((item, j) => (
                  <li key={j} dangerouslySetInnerHTML={{ __html: item }} />
                ))}
              </Tag>
            )
          }

          case 'image': {
            const src = String(block.media_ref ?? '')
            return (
              <figure key={i}>
                {src ? (
                  /* eslint-disable-next-line @next/next/no-img-element -- a legacy
                     remote URL previewed inside the admin. */
                  <img src={src} alt={String(block.alt ?? '')} loading="lazy" />
                ) : null}
                {block.caption ? <figcaption>{String(block.caption)}</figcaption> : null}
              </figure>
            )
          }

          case 'gallery': {
            const images = Array.isArray(block.images)
              ? (block.images as Array<Record<string, unknown>>)
              : []
            return (
              <figure key={i} className="now-bp__gallery">
                <div className="now-bp__grid">
                  {images.map((img, j) => (
                    /* eslint-disable-next-line @next/next/no-img-element -- as above */
                    <img
                      key={j}
                      src={String(img.media_ref ?? '')}
                      alt={String(img.alt ?? '')}
                      loading="lazy"
                    />
                  ))}
                </div>
                {block.caption ? <figcaption>{String(block.caption)}</figcaption> : null}
              </figure>
            )
          }

          case 'separator':
            return <hr key={i} />

          default:
            // Everything the preview has no faithful rendering for says what it
            // is rather than vanishing. A block that disappears from a preview
            // is how a writer concludes it was deleted and then deletes it for
            // real.
            return (
              <div key={i} className="now-bp__opaque">
                {describe(block)}
              </div>
            )
        }
      })}
    </article>
  )
}
