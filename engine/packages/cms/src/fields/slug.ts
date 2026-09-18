import type { Field, FieldHook } from 'payload'

/**
 * The web address field, and the derivation that means a writer never has to
 * think about it.
 *
 * S1.1. Before this, `articles` had no slug at all: the public URL was
 * `legacy_permalink`, correctly marked DO NOT EDIT, so a new article had no
 * reachable address and its cards linked to the homepage.
 */

/**
 * Title → slug.
 *
 * Deliberately identical to `slugify()` in the reader app's `lib/format.ts`,
 * including `&` → " and " rather than dropping it: "Bar & Grill" becoming
 * `bar-grill` reads as a typo in a URL, and `bar-and-grill` does not. The two
 * copies are a real duplication — this package may not import from the web
 * app, and the web app's copy is used for taxonomy labels rather than
 * addresses — so if a third caller ever appears, that is the moment to lift
 * it into a shared package rather than now.
 */
export function slugify(input: string): string {
  return input
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

/**
 * Fill the slug from the title, once.
 *
 * **Only when empty.** Re-deriving on every title edit is the single most
 * common way a CMS breaks its own URLs: a sub-editor sharpens a headline
 * three days after publication and every inbound link dies. So a slug that
 * exists is left alone, whether it was typed, derived earlier, or backfilled
 * from a legacy permalink by migration `20260918_090000_articles_slug`.
 *
 * **A collision is reported, not silently resolved.** The field is `unique`,
 * so a duplicate raises a validation error naming the field. The tempting
 * alternative — quietly appending `-2` — changes the address the writer chose
 * without telling them, and they find out when they paste the link somewhere.
 * Deriving from a title that happens to collide is rare (the archive has zero
 * collisions across 9,201 articles) and being told is the better failure.
 */
const deriveFromTitle: FieldHook = ({ value, data, siblingData }) => {
  if (typeof value === 'string' && value.trim() !== '') return value

  const source = (siblingData as Record<string, unknown> | undefined)?.title ?? (data as Record<string, unknown> | undefined)?.title

  if (typeof source !== 'string' || source.trim() === '') return value

  const derived = slugify(source)
  // An all-punctuation or non-Latin title slugifies to nothing. Returning ''
  // would store an empty string, which is a *value* under a unique index and
  // so collides with the next such article; undefined stays NULL, which
  // Postgres permits many of, and `required` then asks the writer for one.
  return derived === '' ? value : derived
}

/**
 * The address field itself.
 *
 * `required` is safe *because* of the hook above: field-level `beforeValidate`
 * runs before validation, so a writer who never touches this field still
 * passes. What `required` actually buys is that a title which slugifies to
 * nothing cannot be published with no address — it asks, rather than shipping
 * a story nobody can link to.
 */
export const slugField: Field = {
  name: 'slug',
  label: 'Web address',
  type: 'text',
  required: true,
  unique: true,
  index: true,
  admin: {
    description:
      'The last part of the story’s web address. Filled in from the headline when you leave ' +
      'it blank. Once the story is published, changing this breaks every link anyone has ' +
      'already shared, so change it before publishing, not after.',
    // Heebo 13px (docs/DESIGN-SYSTEM.md §5) — a caption beside the display
    // headline above it, not another full-size input. See admin.css's own
    // note on `.now-field--slugline` for what this deliberately does not
    // attempt (a rendered domain prefix).
    className: 'now-field--slugline',
  },
  hooks: {
    beforeValidate: [deriveFromTitle],
  },
}
