import type { Field, SelectField } from 'payload'

import type { VocabularyMap } from '../lib/vocabulary'
import { optionsFor } from '../lib/vocabulary'

/**
 * A `select` field whose options come from the seeded taxonomy
 * (`now_platform.engine.terms`, ARCHITECTURE.md §4) instead of being
 * free-typed. See `src/lib/vocabulary.ts` for how the options are fetched
 * across the platform/city database boundary.
 *
 * `hasMany: true` produces the multi-value facets (cuisine, vibe, occasion,
 * audience, amenities, topic); `hasMany: false` produces the required
 * single-value facets (type, format, price_band).
 */
export function vocabularySelectField(
  vocabulary: VocabularyMap,
  opts: {
    name: string
    label: string
    facetKey: string
    hasMany?: boolean
    required?: boolean
    admin?: SelectField['admin']
  },
): Field {
  const options = optionsFor(vocabulary, opts.facetKey).map((t) => ({
    label: t.parentSlug ? `${t.label} (${t.parentSlug})` : t.label,
    value: t.value,
  }))

  const field: SelectField = {
    name: opts.name,
    label: opts.label,
    type: 'select',
    hasMany: opts.hasMany ?? false,
    required: opts.required ?? false,
    options,
    admin: {
      description:
        options.length === 0
          ? `No "${opts.facetKey}" terms loaded from the platform DB — see PLATFORM_DATABASE_URI. ` +
            'Restart the CMS once the taxonomy is seeded/reachable.'
          : `Constrained to the seeded "${opts.facetKey}" vocabulary (${options.length} terms).`,
      ...opts.admin,
    },
  }
  return field
}
