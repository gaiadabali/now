import assert from 'node:assert/strict'
import { test } from 'node:test'

import { decodeEntities, isSafeHref, sanitizeHtml, sentenceBound, stripTags } from '../src/lib/html.ts'

// ---------------------------------------------------------------------------
// What the archive actually contains
// ---------------------------------------------------------------------------

test('keeps the formatting readers are meant to see', () => {
  assert.equal(
    sanitizeHtml('<strong>Open daily from 5.30pm to 11pm.</strong>'),
    '<strong>Open daily from 5.30pm to 11pm.</strong>',
  )
  assert.equal(sanitizeHtml('traditional Balinese <em>jaje</em>'), 'traditional Balinese <em>jaje</em>')
  assert.equal(sanitizeHtml('Lot North 4<br/>Nusa Dua'), 'Lot North 4<br/>Nusa Dua')
})

test('unwraps WordPress mark-for-colour but keeps the text', () => {
  // Verbatim from now_bali. The <mark> exists only to colour the link; its
  // style is dropped, so keeping the tag would leave an unintended highlight.
  const raw =
    '<a href="mailto:fbreservations@nusaduahotel.com">' +
    '<mark style="background-color:rgba(0, 0, 0, 0)" class="has-inline-color has-vivid-cyan-blue-color">' +
    'fbreservations@nusaduahotel.com</mark></a>'
  assert.equal(
    sanitizeHtml(raw),
    '<a href="mailto:fbreservations@nusaduahotel.com">fbreservations@nusaduahotel.com</a>',
  )
})

test('adds rel to external links only', () => {
  assert.equal(
    sanitizeHtml('<a href="https://www.nusaduahotel.com/facility/">nusaduahotel.com</a>'),
    '<a href="https://www.nusaduahotel.com/facility/" rel="noreferrer noopener">nusaduahotel.com</a>',
  )
  assert.equal(sanitizeHtml('<a href="/dining">Dining</a>'), '<a href="/dining">Dining</a>')
})

// ---------------------------------------------------------------------------
// The reason sanitising happens at all
// ---------------------------------------------------------------------------

test('drops scripts with their contents', () => {
  assert.equal(sanitizeHtml('a<script>alert(1)</script>b'), 'ab')
  assert.equal(sanitizeHtml('a<script src="x.js"></script>b'), 'ab')
  assert.equal(sanitizeHtml('a<SCRIPT>alert(1)</SCRIPT>b'), 'ab')
  // Unclosed: everything from the tag on must go, not just the tag.
  assert.ok(!sanitizeHtml('a<script>alert(1)').includes('alert'))
})

test('drops event handlers, style and class', () => {
  assert.equal(sanitizeHtml('<strong onclick="steal()">hi</strong>'), '<strong>hi</strong>')
  assert.equal(sanitizeHtml('<em style="position:fixed;top:0">hi</em>'), '<em>hi</em>')
  assert.equal(sanitizeHtml('<span class="x" onmouseover="x">hi</span>'), '<span>hi</span>')
})

test('rejects unsafe href schemes, including obfuscated ones', () => {
  assert.equal(sanitizeHtml('<a href="javascript:alert(1)">x</a>'), '<a>x</a>')
  assert.equal(sanitizeHtml('<a href="JaVaScRiPt:alert(1)">x</a>'), '<a>x</a>')
  // Control characters inside the scheme: browsers have honoured these.
  assert.equal(sanitizeHtml('<a href="java\tscript:alert(1)">x</a>'), '<a>x</a>')
  assert.equal(sanitizeHtml('<a href="data:text/html,<script>">x</a>'), '<a>x</a>')
})

test('drops images, iframes and forms', () => {
  assert.equal(sanitizeHtml('<img src=x onerror=alert(1)>'), '')
  assert.equal(sanitizeHtml('<iframe src="https://evil"></iframe>'), '')
  assert.equal(sanitizeHtml('<form><input name=p></form>'), '')
})

test('a stray angle bracket becomes text, not a tag', () => {
  assert.equal(sanitizeHtml('5 < 7 and 9 > 2'), '5 &lt; 7 and 9 > 2')
})

// ---------------------------------------------------------------------------
// Entities
// ---------------------------------------------------------------------------

test('decodes the entities the archive stores in titles', () => {
  // 81 Bali titles carry these; they rendered literally.
  assert.equal(decodeEntities('Catch &amp; Grill'), 'Catch & Grill')
  assert.equal(decodeEntities('GDAS Bali Health &amp; Wellness Resort'), 'GDAS Bali Health & Wellness Resort')
  assert.equal(decodeEntities('It&#8217;s here'), 'It\u2019s here')
  assert.equal(decodeEntities('caf&eacute;'), 'café')
})

test('decodes once, so a literal &amp;amp; survives as &amp;', () => {
  // Decoding to a fixed point would destroy an author's visible "&amp;".
  assert.equal(decodeEntities('A &amp;amp; B'), 'A &amp; B')
})

test('leaves text without entities untouched', () => {
  assert.equal(decodeEntities('Plain title'), 'Plain title')
  assert.equal(decodeEntities('50% & more'), '50% & more')
  assert.equal(decodeEntities('&notanentity;'), '&notanentity;')
})

test('stripTags yields plain text for pull quotes and counts', () => {
  assert.equal(
    stripTags('<strong>Raja&#8217;s</strong> Balinese <em>Cuisine</em>'),
    'Raja\u2019s Balinese Cuisine',
  )
})

// ---------------------------------------------------------------------------
// Balance — the output must not escape the element it is put in
// ---------------------------------------------------------------------------

test('closes tags the archive left open', () => {
  // Found for real: the classification report renders 87 of these strings as
  // sibling <p>s, and an unclosed <strong> in one of them made the browser
  // reconstruct it inside the next — an element the server never rendered, and
  // a hydration failure from there down.
  assert.equal(sanitizeHtml('<strong>Open daily from 5.30pm'), '<strong>Open daily from 5.30pm</strong>')
  assert.equal(
    sanitizeHtml('<a href="https://example.com">Book'),
    '<a href="https://example.com" rel="noreferrer noopener">Book</a>',
  )
})

test('closes nested tags innermost first', () => {
  assert.equal(sanitizeHtml('<em><strong>Both left open'), '<em><strong>Both left open</strong></em>')
})

test('uncrosses tags the source crossed', () => {
  assert.equal(sanitizeHtml('<b><i>x</b>y'), '<b><i>x</i></b>y')
})

test('drops a closing tag that closes nothing of ours', () => {
  // Otherwise it closes something the CALLER opened: the surrounding <p>, or
  // worse, the layout element above it.
  assert.equal(sanitizeHtml('</strong>text'), 'text')
  assert.equal(sanitizeHtml('text</a>'), 'text')
  // The dropped tags around it must not confuse the stack either.
  assert.equal(sanitizeHtml('<p>a</p><p>b</p>'), 'ab')
})

test('br is void and is never closed', () => {
  assert.equal(sanitizeHtml('one<br>two'), 'one<br/>two')
})

// ---------------------------------------------------------------------------
// isSafeHref — the same allowlist, for URLs that are never markup
// ---------------------------------------------------------------------------

test('isSafeHref accepts the schemes the archive legitimately uses', () => {
  assert.equal(isSafeHref('https://www.google.com/maps/embed?pb=!1m18'), true)
  assert.equal(isSafeHref('http://example.com'), true)
  assert.equal(isSafeHref('mailto:hello@example.com'), true)
  assert.equal(isSafeHref('tel:+62361762828'), true)
  assert.equal(isSafeHref('/places/some-venue'), true)
  assert.equal(isSafeHref('#section'), true)
})

test('isSafeHref rejects executable and data schemes, obfuscation included', () => {
  // body_blocks[].url on an embed block becomes an href without ever passing
  // through sanitizeHtml, and React has not sanitised href since v16.
  assert.equal(isSafeHref('javascript:alert(1)'), false)
  assert.equal(isSafeHref('java\tscript:alert(1)'), false)
  assert.equal(isSafeHref(' javascript:alert(1)'), false)
  assert.equal(isSafeHref('JaVaScRiPt:alert(1)'), false)
  assert.equal(isSafeHref('data:text/html,<script>alert(1)</script>'), false)
  assert.equal(isSafeHref('vbscript:msgbox(1)'), false)
  assert.equal(isSafeHref(''), false)
})

test('a raw-text element closed with whitespace still ends where it should', () => {
  // `</script >` — the template literal wrote a literal "s*" instead of \\s*,
  // so this used to fail to match and everything after it was dropped.
  assert.equal(sanitizeHtml('a<script>evil()</script >b'), 'ab')
  assert.equal(sanitizeHtml('a<style>x{}</style\t>b'), 'ab')
})

// ---------------------------------------------------------------------------
// sentenceBound — Edition 2's pull-quote fix
// ---------------------------------------------------------------------------

test('sentenceBound never cuts mid-word', () => {
  // The owner's own example, reconstructed: a naive slice(0, 180) landed
  // inside "Kimpton", so the quote read "...through K...". A word-boundary
  // fallback must land on a real space, never inside a word.
  const long =
    'Guests can expect Kimpton signatures including the complimentary programme, ' +
    'inspiring conversation with other guests and the hotel management through Kimpton Morning Kickstart'
  const out = sentenceBound(long, 90)
  assert.ok(out.endsWith('…'))
  const withoutEllipsis = out.slice(0, -1)
  assert.ok(long.startsWith(withoutEllipsis))
  assert.equal(long[withoutEllipsis.length], ' ')
})

test('sentenceBound prefers a whole sentence when one fits', () => {
  const text = 'This is short. This second sentence is much longer and runs well past the limit given here.'
  assert.equal(sentenceBound(text, 40), 'This is short.')
})

test('sentenceBound returns text unchanged when already within the limit', () => {
  assert.equal(sentenceBound('Short and sweet.', 180), 'Short and sweet.')
})
