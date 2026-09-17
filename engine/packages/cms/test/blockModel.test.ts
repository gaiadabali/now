import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  asBlocks,
  convert,
  countHardBreaks,
  describe as describeBlock,
  hasHardBreaks,
  insertAt,
  moveBy,
  patchAt,
  plainText,
  removeAt,
  replaceAt,
  isEditableHref,
  keepAttribute,
  setHeading,
  shouldUnwrap,
  splitOnHardBreaks,
  wordCount,
  type Block,
} from '../src/fields/blockModel.ts'

/**
 * The property these tests exist for is the first one: a block the writer did
 * not touch must come back byte-identical.
 *
 * `articles.body_blocks` is the cleaner's output stored in `jsonb` with no
 * coercion in either direction, and `verify:body-blocks` proves that round
 * trip over the whole archive. An editing surface is the most likely thing to
 * break it, and it would break it invisibly: a normalisation that drops a
 * `media_ref` or reorders keys produces a diff nobody reads on 4,429 rows.
 * Identity assertions (`assert.equal`, not `deepEqual`) are the point — they
 * check the very same object came back, which no amount of shape-comparing
 * can.
 *
 * `cleanInline` is not tested here. It needs a DOM and this suite runs in bare
 * node; testing it against a stub would be testing the stub. It is exercised
 * by hand in the browser, and its failure mode is cosmetic — a stray tag in
 * text the writer just typed — not data loss.
 */

const sample = (): Block[] => [
  { type: 'paragraph', html: 'First para with <strong>bold</strong>.' },
  { type: 'heading', level: 3, text: 'A HEADING', html: 'A HEADING' },
  {
    type: 'image',
    alt: 'Dance-8216',
    href: null,
    caption: null,
    media_ref: 'https://example.test/a.jpg',
  },
  { type: 'separator' },
]

test('untouched blocks keep their identity through every mutation', () => {
  const blocks = sample()
  const [p, h, img, sep] = blocks

  const edited = patchAt(blocks, 0, { html: 'changed' })
  assert.notEqual(edited[0], p, 'the edited block must be a new object')
  assert.equal(edited[1], h, 'heading must be the same object')
  assert.equal(edited[2], img, 'image must be the same object')
  assert.equal(edited[3], sep, 'separator must be the same object')

  const moved = moveBy(blocks, 0, 2)
  assert.equal(moved[0], h)
  assert.equal(moved[1], img)
  assert.equal(moved[2], p, 'the moved block is moved, not rebuilt')

  const shorter = removeAt(blocks, 1)
  assert.equal(shorter[0], p)
  assert.equal(shorter[1], img)

  const longer = insertAt(blocks, 2, { type: 'paragraph', html: 'new' })
  assert.equal(longer[1], h)
  assert.equal(longer[3], img, 'blocks after the insertion point are untouched')

  assert.deepEqual(blocks, sample(), 'the input array itself is never mutated')
})

test('patching preserves keys the editor has no opinion about', () => {
  const blocks = sample()
  const patched = patchAt(blocks, 2, { alt: 'A better description' })
  const img = patched[2]
  assert.equal(img.alt, 'A better description')
  assert.equal(img.media_ref, 'https://example.test/a.jpg', 'media_ref survives')
  assert.equal(img.href, null, 'an explicit null is not dropped')
  assert.ok('caption' in img, 'a key the edit did not mention is still present')
})

test('out-of-range operations are no-ops, not corruption', () => {
  const blocks = sample()
  assert.equal(replaceAt(blocks, -1, { type: 'paragraph' }), blocks)
  assert.equal(replaceAt(blocks, 99, { type: 'paragraph' }), blocks)
  assert.equal(removeAt(blocks, 99), blocks)
  assert.equal(moveBy(blocks, 0, -1), blocks, 'moving the first block up changes nothing')
  assert.equal(moveBy(blocks, 3, 1), blocks, 'moving the last block down changes nothing')
  assert.equal(patchAt(blocks, 99, { html: 'x' }), blocks)
})

test('insertAt clamps rather than producing holes', () => {
  const blocks = sample()
  const atEnd = insertAt(blocks, 999, { type: 'separator' })
  assert.equal(atEnd.length, 5)
  assert.equal(atEnd[4].type, 'separator')
  const atStart = insertAt(blocks, -5, { type: 'separator' })
  assert.equal(atStart[0].type, 'separator')
  assert.ok(atEnd.every(Boolean), 'no undefined slots')
})

test('asBlocks tolerates the shapes a loose validator allows through', () => {
  assert.deepEqual(asBlocks(null), [])
  assert.deepEqual(asBlocks('not an array'), [])
  assert.deepEqual(asBlocks({ type: 'paragraph' }), [], 'a bare object is not a block array')
  // A future block type must survive: `bodyBlocks.ts` validates loosely so the
  // cleaner can add one without breaking saves, and this has to match.
  const future = asBlocks([{ type: 'timeline', steps: [] }, null, 42, { noType: true }])
  assert.equal(future.length, 1)
  assert.equal(future[0].type, 'timeline')
})

test('heading edits write both stored fields', () => {
  // The archive stores `text` and `html` on every heading. Writing one and not
  // the other leaves them disagreeing, and different renderers in this repo
  // read different ones.
  const next = setHeading({ type: 'heading', level: 3, text: 'Old', html: 'Old' }, 'New', 2)
  assert.equal(next.text, 'New')
  assert.equal(next.html, 'New')
  assert.equal(next.level, 2)
})

test('converting between paragraph and heading keeps the words', () => {
  const asHeading = convert({ type: 'paragraph', html: 'Some <em>words</em> here' }, 'heading')
  assert.equal(asHeading.type, 'heading')
  assert.equal(asHeading.text, 'Some words here', 'inline markup is dropped, the text is not')
  assert.equal(asHeading.html, asHeading.text)

  const back = convert({ type: 'heading', level: 2, text: 'A title', html: 'A title' }, 'paragraph')
  assert.equal(back.type, 'paragraph')
  assert.equal(back.html, 'A title')

  const unchanged: Block = { type: 'paragraph', html: 'x' }
  assert.equal(convert(unchanged, 'paragraph'), unchanged, 'converting to its own type is a no-op')
})

test('plainText strips markup without gluing words together', () => {
  assert.equal(plainText('<p>one</p><p>two</p>'), 'one two')
  assert.equal(plainText('a <strong>b</strong> c'), 'a b c')
  assert.equal(plainText(''), '')
})

test('plainText decodes the entities this archive actually contains', () => {
  // This function must give the SAME answer on the server and in the browser,
  // because its output reaches the rendered word count. It used to use
  // `textContent` in the browser and a regex on the server, and the two
  // disagreed about exactly these inputs — which React reported as a hydration
  // mismatch and repaired by rebuilding the whole editor on the client.
  assert.equal(plainText('Fish &amp; chips'), 'Fish & chips')
  assert.equal(plainText('a&nbsp;b'), 'a b', 'a non-breaking space is a word boundary')
  assert.equal(plainText('&lt;tag&gt;'), '<tag>')
  assert.equal(plainText('&#8217;'), '’', 'numeric escapes are the common ones here')
  assert.equal(plainText('&amp;lt;'), '&lt;', 'decoding happens once, not twice')
  assert.equal(plainText('&unknownentity;'), '&unknownentity;', 'anything else survives as text')
})

test('word counts do not depend on there being a DOM', () => {
  // The regression guard for the hydration bug: the count is a pure function
  // of the string, so a server render and a client render cannot disagree.
  const blocks: Block[] = [{ type: 'paragraph', html: 'Fish &amp; chips&nbsp;today' }]
  assert.equal(wordCount(blocks), 4)
})

test('wordCount counts prose and ignores captions and alt text', () => {
  const blocks: Block[] = [
    { type: 'paragraph', html: 'one two three' },
    { type: 'heading', level: 2, text: 'four five', html: 'four five' },
    { type: 'list', ordered: false, items: ['six seven', 'eight'] },
    // Neither of these is prose a writer is counting.
    { type: 'image', alt: 'nine ten eleven twelve', caption: 'thirteen', media_ref: 'x' },
    { type: 'separator' },
  ]
  assert.equal(wordCount(blocks), 8)
})

test('describe says something useful for every block the editor will not edit', () => {
  assert.equal(describeBlock({ type: 'separator' }), 'Section break')
  assert.equal(describeBlock({ type: 'gallery', images: [1, 2, 3] }), 'Gallery — 3 images')
  assert.equal(describeBlock({ type: 'columns', columns: [[], []] }), 'Columns — 2 of them')
  assert.equal(
    describeBlock({ type: 'raw_html', html: '<table>', reason: 'table' }),
    'table',
    'raw_html shows the cleaner\'s own reason, which is the only clue a writer gets',
  )
  assert.equal(describeBlock({ type: 'image', alt: '', caption: 'A caption' }), 'A caption')
  assert.equal(describeBlock({ type: 'timeline' }), 'timeline', 'an unknown type names itself')
})

/**
 * Splitting run-on paragraphs — the fix for what a screenshot of the real
 * editor turned up: a whole article stored as one `paragraph` block with ten
 * newlines in it. Measured across both cities, 11,042 paragraph blocks in
 * 3,675 articles carry a newline, and 163 articles are a single block.
 *
 * HTML collapses those newlines to spaces, so the reader gets one run-on
 * paragraph. The preview pane showed that correctly while the editor's own
 * `white-space: pre-wrap` drew them as separate paragraphs — the editor was
 * the one lying, and these tests are the fix for the content rather than for
 * the rendering.
 */

const NL = '\n'

test('a newline is a paragraph break and gets split', () => {
  const pieces = splitOnHardBreaks({
    type: 'paragraph',
    html: `First paragraph.${NL}Second paragraph.${NL}${NL}Third.`,
  })
  assert.equal(pieces.length, 3)
  assert.deepEqual(
    pieces.map((p) => p.html),
    ['First paragraph.', 'Second paragraph.', 'Third.'],
  )
  assert.ok(pieces.every((p) => p.type === 'paragraph'))
})

test('a SINGLE <br> is left alone, because it is usually load-bearing', () => {
  // An address, opening hours, a name over a phone number. Splitting those
  // into separate paragraphs spaces them apart and reads worse than the
  // run-on it was trying to fix.
  const one: Block = { type: 'paragraph', html: 'Jalan Raya 1<br>Seminyak<br>+62 361 000' }
  assert.equal(hasHardBreaks(one), false)
  assert.equal(splitOnHardBreaks(one)[0], one, 'unchanged, and the same object')
})

test('two or more consecutive <br> is a paragraph break', () => {
  const pieces = splitOnHardBreaks({
    type: 'paragraph',
    html: 'One.<br><br>Two.<br /> <br/>Three.',
  })
  assert.deepEqual(
    pieces.map((p) => p.html),
    ['One.', 'Two.', 'Three.'],
  )
})

test('splitting is a no-op when there is nothing to split', () => {
  const plain: Block = { type: 'paragraph', html: 'Just one paragraph.' }
  assert.equal(
    splitOnHardBreaks(plain)[0],
    plain,
    'the same object back, so a caller can apply it blindly',
  )
  assert.equal(splitOnHardBreaks(plain).length, 1)
})

test('splitting drops empty fragments rather than making empty blocks', () => {
  const pieces = splitOnHardBreaks({
    type: 'paragraph',
    html: `A.${NL}${NL}${NL}   ${NL}<b> </b>${NL}B.`,
  })
  assert.deepEqual(
    pieces.map((p) => p.html),
    ['A.', 'B.'],
  )
})

test('splitting copies keys it has no opinion about onto every piece', () => {
  const pieces = splitOnHardBreaks({
    type: 'paragraph',
    html: `A${NL}B`,
    futureAttr: 'keep me',
  })
  assert.equal(pieces.length, 2)
  assert.ok(pieces.every((p) => p.futureAttr === 'keep me'))
})

test('only prose blocks are candidates for splitting', () => {
  // An image has no `html`. A raw_html block's newlines sit inside markup the
  // importer could not classify, and splitting those would produce fragments
  // of a table.
  assert.equal(hasHardBreaks({ type: 'image', alt: `x${NL}y`, media_ref: 'z' }), false)
  assert.equal(hasHardBreaks({ type: 'raw_html', html: `<table>${NL}<tr>` }), false)
  assert.equal(hasHardBreaks({ type: 'quote', html: `a${NL}b` }), true, 'a quote is prose')
})

test('hasHardBreaks is stable across repeated calls', () => {
  // A `g`-flagged RegExp carries `lastIndex` between `.test()` calls and would
  // alternate true/false on the same input. This is the guard for that.
  const block: Block = { type: 'paragraph', html: `a${NL}b` }
  assert.equal(hasHardBreaks(block), true)
  assert.equal(hasHardBreaks(block), true)
  assert.equal(hasHardBreaks(block), true)
})

test('countHardBreaks counts the blocks that need fixing', () => {
  assert.equal(
    countHardBreaks([
      { type: 'paragraph', html: `a${NL}b` },
      { type: 'paragraph', html: 'clean' },
      { type: 'paragraph', html: `c${NL}${NL}d` },
      { type: 'image', alt: 'x' },
    ]),
    2,
  )
})

/**
 * The markup policy, checked as data.
 *
 * `cleanInline` itself needs a DOM and this suite runs in bare node, so the
 * decisions it makes are exported as pure functions and tested here. That
 * split is not academic: the first version of the policy was an ALLOW-list of
 * six inline tags, and a test of the real surface caught it deleting a
 * photograph out of a paragraph — `<img>` was not on the list and unwrapping a
 * void element removes it.
 *
 * Measured afterwards across both cities, inside prose blocks: 1,282 `<img>`,
 * 1,000 `<sup>`, 42 `<iframe>`. An allow-list would have destroyed all of them
 * in any paragraph a writer clicked into.
 */

test('presentational wrappers are unwrapped', () => {
  for (const tag of ['SPAN', 'MARK', 'DIV', 'P', 'FONT', 'span', 'mark']) {
    assert.equal(shouldUnwrap(tag), true, `${tag} should be unwrapped`)
  }
})

test('anything carrying content is preserved, including tags nobody listed', () => {
  // This is the regression guard for the deleted image, and for the whole
  // class: an unrecognised tag in a twenty-year archive is far likelier to be
  // somebody's content than somebody's mistake.
  for (const tag of ['IMG', 'IFRAME', 'SUP', 'SUB', 'SMALL', 'TIME', 'U', 'S', 'ABBR', 'TIMELINE']) {
    assert.equal(shouldUnwrap(tag), false, `${tag} must survive`)
  }
})

test('only meaning-bearing attributes are kept', () => {
  assert.equal(keepAttribute('a', 'href'), true)
  assert.equal(keepAttribute('IMG', 'src'), true)
  assert.equal(keepAttribute('img', 'alt'), true, 'alt is an accessibility obligation')
  assert.equal(keepAttribute('time', 'datetime'), true)

  // Appearance, not meaning. `width` in particular is a 2015 layout decision
  // and the reader's CSS is a better answer to it than the number.
  assert.equal(keepAttribute('img', 'width'), false)
  assert.equal(keepAttribute('img', 'class'), false)
  assert.equal(keepAttribute('a', 'style'), false)
  assert.equal(keepAttribute('a', 'onclick'), false)
  assert.equal(keepAttribute('strong', 'anything'), false, 'a tag with no entry keeps nothing')
})

test('hrefs a reader can safely follow are kept, and only those', () => {
  for (const ok of [
    'https://example.test/a',
    'http://example.test',
    '/relative',
    '#anchor',
    'mailto:someone@example.test',
    'tel:+62361000',
    '  https://example.test  ',
  ]) {
    assert.equal(isEditableHref(ok), true, `${ok} should be allowed`)
  }
  for (const bad of ['javascript:alert(1)', 'data:text/html;base64,x', 'vbscript:x', 'file:///etc']) {
    assert.equal(isEditableHref(bad), false, `${bad} must be refused`)
  }
})

test('splitting keeps a fragment that is only an image', () => {
  // The regression guard for a deleted photograph. The filter used to be
  // "does this fragment have visible text", and a fragment holding nothing but
  // <img src=…> has none — so splitting a real article threw its image away.
  // Caught by driving the editor over real content, not by reading the code.
  const pieces = splitOnHardBreaks({
    type: 'paragraph',
    html: `Before the picture.${NL}<img src="https://example.test/a.jpg" alt="A thing">${NL}After it.`,
  })
  assert.equal(pieces.length, 3)
  assert.match(String(pieces[1].html), /<img/, 'the image is its own paragraph, not missing')
  assert.deepEqual(
    [pieces[0].html, pieces[2].html],
    ['Before the picture.', 'After it.'],
  )
})

test('splitting keeps other media-only fragments too', () => {
  for (const tag of [
    '<iframe src="https://example.test/e"></iframe>',
    '<video src="x.mp4"></video>',
    '<table><tr><td>a</td></tr></table>',
  ]) {
    const pieces = splitOnHardBreaks({ type: 'paragraph', html: `A${NL}${tag}${NL}B` })
    assert.equal(pieces.length, 3, `${tag.slice(0, 20)} should survive`)
  }
})

test('splitting still drops fragments that are genuinely nothing', () => {
  const pieces = splitOnHardBreaks({
    type: 'paragraph',
    html: `A.${NL}<br>${NL}<b></b>${NL}   ${NL}B.`,
  })
  assert.deepEqual(pieces.map((p) => p.html), ['A.', 'B.'])
})
