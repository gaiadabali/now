import type { Field } from 'payload'

/**
 * `articles.body_blocks` — ARCHITECTURE.md §5.
 *
 * Deliberately a `json` field, NOT Payload rich text / native `blocks`.
 * Two reasons:
 *
 *   1. E1.2's cleaner already emits a stable, versioned block-array shape
 *      (`heading`, `paragraph`, `image`, `gallery`, `list`, `quote`,
 *      `embed`, `separator`, `columns`, `raw_html`) verified over all 4,772
 *      articles at ~0% content loss. Re-modelling that as Payload's Lexical
 *      rich-text AST would require a lossy two-way converter and would
 *      make E1.8's loader output effectively unusable without one.
 *   2. Payload's `json` field type maps straight to a `jsonb` column on the
 *      postgres adapter with no schema coercion in either direction — what
 *      E1.8 writes is byte-for-byte what an editor sees and what a GET
 *      returns. That is the round-trip guarantee this ticket's acceptance
 *      criteria asks for.
 *
 * Validation here is intentionally loose: it checks the top-level shape
 * (an array of objects, each with a recognised `type`) but does not
 * enforce every per-type sub-field, so a `raw_html.reason` value E1.2 adds
 * later, or a new block type, doesn't hard-fail editor saves. It exists to
 * catch obviously-wrong input (e.g. pasting a single object instead of an
 * array) without becoming a second, drifting copy of E1.2's schema.
 */

const KNOWN_BLOCK_TYPES = new Set([
  'heading',
  'paragraph',
  'image',
  'gallery',
  'list',
  'quote',
  'embed',
  'separator',
  'columns',
  'raw_html',
])

export const bodyBlocksField: Field = {
  name: 'bodyBlocks',
  label: 'Body',
  type: 'json',
  admin: {
    /**
     * The stored shape is unchanged and everything above still holds. What
     * changed is who has to look at it: a `json` field renders as a code
     * editor, and an article here averages 15 blocks and runs to 596, so
     * fixing a typo meant finding the sentence inside a quoted string and not
     * breaking the escaping around it. This field's own description used to
     * warn "edit with care — this is the loader's output format, not prose",
     * which was accurate, and was also an admission that the surface had been
     * built for the importer rather than for the person using it.
     *
     * `BodyBlocksEditor` edits the same array in place — `blockModel.ts`
     * guarantees, with tests, that a block the writer did not touch comes back
     * as the very same object — and puts the body beside it at reader
     * typography. Registered by path through the generated importMap, like
     * every other custom component in this config.
     */
    components: { Field: '/fields/BodyBlocksEditor#BodyBlocksEditor' },
    description:
      'The article itself. Write on the left, read it back on the right. Every action is in ' +
      'the bar at the top and acts on whichever block you are in. Blocks you do not touch are ' +
      'saved back exactly as they were.',
  },
  validate: (value: unknown) => {
    if (value === undefined || value === null) return true // optional until E1.8 loads content
    if (!Array.isArray(value)) return 'body_blocks must be an array of block objects'

    for (let i = 0; i < value.length; i++) {
      const block = value[i]
      if (typeof block !== 'object' || block === null || Array.isArray(block)) {
        return `body_blocks[${i}] must be an object`
      }
      const type = (block as Record<string, unknown>).type
      if (typeof type !== 'string' || !KNOWN_BLOCK_TYPES.has(type)) {
        return `body_blocks[${i}].type "${String(type)}" is not a recognised block type (${Array.from(
          KNOWN_BLOCK_TYPES,
        ).join(', ')})`
      }
    }
    return true
  },
}
