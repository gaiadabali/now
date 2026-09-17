import type { ProseBlock } from '@/lib/bodyBlocks'

/**
 * `body_blocks` on screen as an article instead of as an array.
 *
 * Every `html` string reaching `dangerouslySetInnerHTML` below was put through
 * `sanitizeHtml` in lib/bodyBlocks.ts, which is the same allowlist scanner the
 * reader site uses. The attribute's name is louder than the risk here for the
 * same reason it is on the reader's article page: the alternative is React
 * escaping the archive's own formatting and printing `<strong>` at the person
 * trying to read it — which is, almost exactly, the complaint that produced
 * this whole surface.
 *
 * Headings are rendered two levels down from where they are stored. A body
 * `h2` is `h4` here, because the report's own `<h1>` is the article title and
 * its `<h2>`s are the report's sections; letting body headings back in at
 * their stored level would put six `<h2>`s in the outline with no relationship
 * to the page's structure.
 */
export function ArticleProse({ blocks }: { blocks: ProseBlock[] }) {
  return (
    <div className="classify__prose">
      {blocks.map((block, i) => {
        switch (block.kind) {
          case 'heading': {
            const Tag = `h${Math.min(block.level + 2, 6)}` as 'h4' | 'h5' | 'h6'
            return <Tag key={i}>{block.text}</Tag>
          }

          case 'paragraph':
            return <p key={i} dangerouslySetInnerHTML={{ __html: block.html }} />

          case 'list': {
            const List = block.ordered ? 'ol' : 'ul'
            return (
              <List key={i}>
                {block.items.map((item, j) => (
                  <li key={j} dangerouslySetInnerHTML={{ __html: item }} />
                ))}
              </List>
            )
          }

          case 'quote':
            return (
              <blockquote key={i}>
                <div dangerouslySetInnerHTML={{ __html: block.html }} />
                {block.cite ? <cite>{block.cite}</cite> : null}
              </blockquote>
            )

          case 'figure':
            // The image itself is not rendered — see lib/bodyBlocks.ts for why
            // (in-body `media_ref` is still a WordPress URL on the site this
            // replaces). What is shown is the part that carries signal.
            return (
              <p key={i} className="classify__figure">
                <span className="classify__figure-tag">image</span>
                {block.alt || block.caption}
              </p>
            )

          case 'gallery':
            return (
              <p key={i} className="classify__figure">
                <span className="classify__figure-tag">gallery</span>
                {block.alts.length
                  ? `${block.alts.length} images — ${block.alts.slice(0, 4).join('; ')}${
                      block.alts.length > 4 ? '…' : ''
                    }`
                  : 'images, no alt text stored'}
              </p>
            )

          case 'embed':
            return (
              <p key={i} className="classify__figure">
                <span className="classify__figure-tag">{block.provider ?? 'embed'}</span>
                {block.url ? (
                  <a href={block.url} rel="noreferrer noopener" target="_blank">
                    {block.url}
                  </a>
                ) : (
                  // Not a scheme an href may use (see lib/bodyBlocks.ts). Shown
                  // as text so the reviewer can still see what is stored.
                  <span title="not a linkable URL">{block.raw || 'no URL stored'}</span>
                )}
              </p>
            )

          case 'raw':
            return (
              <div key={i} className="classify__raw">
                <span className="classify__figure-tag">
                  raw html{block.reason ? ` — ${block.reason}` : ''}
                </span>
                <div dangerouslySetInnerHTML={{ __html: block.html }} />
              </div>
            )

          case 'separator':
            return <hr key={i} />
        }
      })}
    </div>
  )
}
