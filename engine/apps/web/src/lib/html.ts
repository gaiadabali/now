/**
 * Rendering legacy WordPress body HTML safely.
 *
 * The archive's paragraphs are HTML — `bodyBlocks[].html`, and the field is
 * named that because it is. The reader rendered them with `<p>{p}</p>`, which
 * makes React escape the markup and print it: readers saw
 * `<strong>Open daily from 5.30pm</strong>` and whole mailto anchors, in the
 * body of every article that had any formatting at all.
 *
 * Fixing that means emitting real HTML, which means sanitising it first. The
 * content comes from our own database, but it came into our database from
 * twenty years of WordPress, and "our own data" is exactly how stored XSS
 * survives. So this is an ALLOWLIST: anything not named here is dropped.
 *
 * Hand-written rather than pulled from npm because the alternative is DOMPurify
 * plus jsdom in a server bundle for a job this size, and because the artifact
 * CSP forbids loading a sanitiser at runtime. It is deliberately small enough
 * to audit in one sitting.
 */

/** Inline tags worth keeping. Nothing that can execute, load, or position. */
const ALLOWED_TAGS = new Set([
  'a',
  'b',
  'strong',
  'i',
  'em',
  'u',
  's',
  'br',
  'span',
  'sup',
  'sub',
  'code',
  'abbr',
  'q',
  'cite',
])

/**
 * `mark` is deliberately NOT allowed even though the archive is full of it.
 *
 * WordPress's editor used `<mark style="background-color:rgba(0,0,0,0)"
 * class="has-inline-color has-vivid-cyan-blue-color">` purely to colour link
 * text. Keeping the tag without its style — and style is never kept — leaves a
 * highlight the author never intended, so the honest thing is to unwrap it and
 * keep the text.
 */
const UNWRAP_TAGS = new Set(['mark', 'font', 'p', 'div'])

/** Per-tag attribute allowlist. Everything else, `style` and `class` and every
 *  `on*` handler included, is dropped. */
const ALLOWED_ATTRS: Record<string, Set<string>> = {
  a: new Set(['href', 'title']),
  abbr: new Set(['title']),
  q: new Set(['cite']),
}

/** Schemes a link may use. `javascript:` and `data:` are the reason this exists. */
const SAFE_HREF = /^(https?:|mailto:|tel:|#|\/)/i

/**
 * May this URL be an `href`?
 *
 * Exported because `sanitizeHtml` is not the only place a stored URL becomes a
 * link. `body_blocks[].url` on an `embed` block is a bare string field, never
 * markup, so it never passes through the scanner below — and React stopped
 * sanitising `href` values in v16, so `<a href={url}>` with a stored
 * `javascript:` URL is a working XSS. Same allowlist, same reasoning, one
 * definition: a second copy of this rule is a second chance to get it wrong.
 *
 * Whitespace and control characters are stripped before the test because
 * `java\tscript:` is a scheme browsers have historically honoured.
 */
export function isSafeHref(url: string): boolean {
  return SAFE_HREF.test(Array.from(url).filter((c) => c.charCodeAt(0) > 0x20).join(''))
}

const ENTITIES: Record<string, string> = {
  amp: '&',
  lt: '<',
  gt: '>',
  quot: '"',
  apos: "'",
  nbsp: '\u00a0',
  ndash: '–',
  mdash: '—',
  lsquo: '\u2018',
  rsquo: '\u2019',
  ldquo: '\u201c',
  rdquo: '\u201d',
  hellip: '…',
  eacute: 'é',
  egrave: 'è',
  agrave: 'à',
  ccedil: 'ç',
  uuml: 'ü',
  ouml: 'ö',
  auml: 'ä',
}

/**
 * `&amp;` → `&`, `&#8217;` → `’`.
 *
 * Titles are plain text in the view model, so React escapes them on render and
 * a stored entity shows as itself: 81 Bali titles read "Catch &amp; Grill" on
 * the page. The entity is in the database, so decoding is a read concern.
 *
 * Runs once, not to a fixed point: decoding repeatedly would turn a literal
 * `&amp;amp;` — which is how an author writes a visible `&amp;` — into `&`.
 */
export function decodeEntities(text: string): string {
  if (!text.includes('&')) return text
  return text.replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]*);/g, (match, body: string) => {
    if (body[0] === '#') {
      const code =
        body[1] === 'x' || body[1] === 'X'
          ? Number.parseInt(body.slice(2), 16)
          : Number.parseInt(body.slice(1), 10)
      // Reject NaN, NUL and anything outside Unicode. A malformed numeric
      // entity stays as written rather than becoming a replacement character.
      if (!Number.isFinite(code) || code <= 0 || code > 0x10ffff) return match
      try {
        return String.fromCodePoint(code)
      } catch {
        return match
      }
    }
    return ENTITIES[body.toLowerCase()] ?? match
  })
}

/** Every tag removed, entities decoded. For text that must not be markup:
 *  pull quotes, meta descriptions, reading-time word counts. */
export function stripTags(html: string): string {
  return decodeEntities(html.replace(/<[^>]*>/g, '')).replace(/\s+/g, ' ').trim()
}

/**
 * A pull quote's first complete sentence, or nothing — never a truncation.
 *
 * Two rounds of the same defect. Round one was `quote.slice(0,
 * 180).trimEnd() + '…'`, a raw character count that ended "through K…", a
 * name split in half. Round two (`sentenceBound`, since removed) fixed the
 * mid-word cut but still fell back to a WORD-boundary truncation when the
 * chosen paragraph's own first sentence ran past the limit, which is how a
 * real pull quote still ended "...management through…" — grammatically
 * intact at the cut, and still not what the paragraph said. A magazine
 * does not truncate a pull quote, full stop: if the sentence does not fit,
 * this returns nothing, and the caller (`[slug]/page.tsx`) tries the next
 * paragraph rather than trim the one it has.
 *
 * The match looks for the FIRST `.`/`!`/`?` followed by whitespace or the
 * end of the string — end-of-string matters because a paragraph's last
 * sentence often has no trailing space to find. If that first sentence's
 * own length is within `limit`, it is returned whole; if the paragraph has
 * no sentence-ending punctuation at all, or its first sentence alone
 * exceeds `limit`, this returns `null`.
 *
 * One more rejection, found by actually reading what this returned against
 * a real article: a trailing address block — "Kimpton Suntaya Bali
 * Ubud<br/>Jl. Bisma No. 31, Ubud" in the source — had its `<br>` stripped
 * by `stripTags` with no space put back, so the plain text read "...Bali
 * UbudJl. Bisma...", and "Jl." (Indonesian "Jalan", street) read as a
 * sentence-ending abbreviation. The result was a pull quote reading
 * "Kimpton Suntaya Bali UbudJl." — grammatically a "sentence" by the regex
 * above, and gibberish. A lowercase letter immediately followed by an
 * uppercase one with no space between is not something ordinary prose
 * produces; it is what a missing space at a stripped tag boundary looks
 * like, so a candidate containing one is rejected here rather than
 * returned — which, through the same "try the next paragraph" loop that
 * already exists in `[slug]/page.tsx`, is what keeps a non-prose block
 * like this one from ever being offered as a quote at all.
 */
export function firstWholeSentence(text: string, limit = 180): string | null {
  const trimmed = text.trim()
  if (!trimmed) return null
  const match = /^.*?[.!?](?=\s|$)/.exec(trimmed)
  if (!match) return null
  const sentence = match[0].trim()
  if (sentence.length === 0 || sentence.length > limit) return null
  if (/[a-z][A-Z]/.test(sentence)) return null
  return sentence
}

function escapeText(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function sanitizeAttrs(tag: string, raw: string): string {
  const allowed = ALLOWED_ATTRS[tag]
  if (!allowed) return ''

  const out: string[] = []
  const attr = /([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*("([^"]*)"|'([^']*)'|([^\s"'>]+))/g
  let m: RegExpExecArray | null
  while ((m = attr.exec(raw)) !== null) {
    const name = m[1].toLowerCase()
    if (!allowed.has(name)) continue
    const value = decodeEntities(m[3] ?? m[4] ?? m[5] ?? '')
    if (name === 'href') {
      // Whitespace and control characters are stripped before testing, because
      // `java\tscript:` is a scheme browsers have historically honoured.
      const cleaned = Array.from(value).filter((c) => c.charCodeAt(0) > 0x20).join('')
      if (!isSafeHref(cleaned)) continue
      out.push(`href="${escapeText(cleaned)}"`)
      continue
    }
    out.push(`${name}="${escapeText(value)}"`)
  }
  return out.length ? ' ' + out.join(' ') : ''
}

/** Elements whose CONTENT is not markup. Unwrapping these would dump code
 *  into the page as text, so they are skipped whole. */
const RAW_TEXT_TAGS = new Set([
  'script',
  'style',
  'iframe',
  'object',
  'embed',
  'svg',
  'math',
  'template',
  'noscript',
  'xmp',
])

/**
 * Matches ONE complete tag at position 0, quoted attribute values included, so
 * a `>` inside an attribute does not end the tag early.
 */
const TAG_AT_START =
  /^<\s*(\/?)\s*([a-zA-Z][a-zA-Z0-9]*)((?:\s+[^\s=/>]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*))?)*)\s*\/?\s*>/

/**
 * Returns HTML containing only allowlisted tags and attributes.
 *
 * A SCANNER, not a sequence of regex passes. The pass-based version had a real
 * hole, found by the test below: stripping `<script...>` first could cut
 * through the middle of an attribute value, and the leftover
 * `<a href="data:text/html,` — an unterminated tag — then slipped past the
 * final escape, because that escape had to spare the `<` of tags it had just
 * written. Scanning once removes the whole class of problem: at any `<` the
 * input either yields a complete, parseable tag or the character is escaped to
 * `&lt;` and treated as text. There is no third outcome.
 *
 * The output is also BALANCED, which it was not until the team editor's
 * classification report put 87 of these strings on one page and React's
 * hydration started failing on it. The archive is full of paragraphs with an
 * `<a>` or a `<strong>` that is never closed — WordPress tolerated it — and
 * this function used to hand that straight through. Inside a single
 * `dangerouslySetInnerHTML` that looks harmless, because `</p>` appears to
 * close it. It does not: HTML's adoption agency algorithm keeps an unclosed
 * formatting element on the list of active formatting elements and
 * RE-CREATES it inside the next element, so the browser's DOM gains a node
 * the server never rendered, every following sibling shifts by one, and
 * hydration fails from there down.
 *
 * That is the visible symptom. The reason it is worth fixing in the sanitiser
 * rather than in the one page that noticed: unbalanced output means this
 * function's result does not stay inside the element it is put in. An
 * unclosed `<a href="http://spam">` in the last paragraph of an article
 * silently turns the byline, the tags and the related-articles rail into part
 * of that link. Reconstruction is what makes it escape, and a sanitiser whose
 * output escapes its container is not finished sanitising.
 *
 * Unmatched CLOSING tags are dropped for the mirror-image reason: `</strong>`
 * with nothing open closes something the caller opened, not something this
 * string did.
 */
export function sanitizeHtml(html: string): string {
  if (!html) return ''

  let out = ''
  let i = 0
  // Tags opened and not yet closed, innermost last.
  const open: string[] = []

  while (i < html.length) {
    const lt = html.indexOf('<', i)
    if (lt === -1) {
      out += html.slice(i)
      break
    }
    out += html.slice(i, lt)

    // Comments, doctypes, CDATA and processing instructions: dropped whole.
    if (html.startsWith('<!--', lt)) {
      const end = html.indexOf('-->', lt + 4)
      i = end === -1 ? html.length : end + 3
      continue
    }
    if (html.startsWith('<!', lt) || html.startsWith('<?', lt)) {
      const end = html.indexOf('>', lt)
      i = end === -1 ? html.length : end + 1
      continue
    }

    const m = TAG_AT_START.exec(html.slice(lt))
    if (!m) {
      // Not a well-formed tag — a comparison, or a truncated one. Text.
      out += '&lt;'
      i = lt + 1
      continue
    }

    const [matched, closing, rawTag, rawAttrs] = m
    const tag = rawTag.toLowerCase()
    i = lt + matched.length

    if (RAW_TEXT_TAGS.has(tag)) {
      if (!closing) {
        // Skip to the matching close, or to the end if it never closes.
        // `\\s`, not `\s`: inside a template literal `\s` is not a recognised
        // escape, so JS drops the backslash and the pattern becomes a LITERAL
        // "s*" — `</script >` then failed to match and everything after it was
        // dropped as still-inside-the-script. Content loss rather than a
        // sanitiser bypass, but silent either way.
        const close = new RegExp(`</\\s*${tag}\\s*>`, 'i').exec(html.slice(i))
        i = close ? i + close.index + close[0].length : html.length
      }
      continue
    }

    if (UNWRAP_TAGS.has(tag) || !ALLOWED_TAGS.has(tag)) continue
    if (closing) {
      // Close back to the matching opener, so `<b><i></b>` becomes
      // `<b><i></i></b>` rather than the crossed pair the source wrote.
      // Nothing matching means nothing of ours is open: drop it.
      const at = open.lastIndexOf(tag)
      if (at === -1) continue
      for (let d = open.length - 1; d >= at; d--) out += `</${open[d]}>`
      open.length = at
      continue
    }
    if (tag === 'br') {
      // Void: never pushed, because there is nothing to close.
      out += '<br/>'
      continue
    }

    const attrs = sanitizeAttrs(tag, rawAttrs)
    // Every external link gets rel: `noopener` closes the window.opener hole
    // and `noreferrer` keeps our URLs out of third-party logs. Applied here
    // rather than trusted from the source markup, which is inconsistent.
    const rel = tag === 'a' && /href="https?:/i.test(attrs) ? ' rel="noreferrer noopener"' : ''
    out += `<${tag}${attrs}${rel}>`
    open.push(tag)
  }

  // Whatever the source left hanging, close here — innermost first.
  for (let d = open.length - 1; d >= 0; d--) out += `</${open[d]}>`

  return out
}
