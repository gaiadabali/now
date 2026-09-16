import 'server-only'

import pg from 'pg'

import { locationTree } from '@/lib/payload'
import { getSiteConfig } from '@/lib/site'

/**
 * The registration preference picker and what it writes (E8.4).
 *
 * ARCHITECTURE §17 specifies the flow and gives the budget — "keep under 30
 * seconds" — and §10 says what the answers are *for*:
 *
 *     α = n_meaningful / (n_meaningful + 20)
 *     taste = α · revealed + (1 − α) · stated_seed
 *
 * These picks are the `stated_seed`. A reader with no history is 100% what
 * they told us; at 20 meaningful interactions it is an even blend; and the
 * picks never stop counting. That is why they are worth collecting before a
 * single beacon event exists.
 *
 * ## Every option is a vocabulary term, never free text
 *
 * The picker is built from `engine.terms` — the same vocabulary the classifier
 * writes against and `entity_terms` joins on. A parallel list of "interests"
 * would drift from the taxonomy within a month and then match nothing.
 *
 * It also means a stated-preference feed works **today**: `entity_terms` is
 * populated (17,237 Jakarta / 15,804 Bali), unlike `articles.primary_type`,
 * which is NULL archive-wide and is what F50 blocks the rails on.
 *
 * ## Why slugs and not term ids
 *
 * A term's uuid is stable within one database and **different in every
 * other**: the vocabulary is seeded by migration (`vocabulary_delta_140_terms`
 * and friends), so the same `eat` term has one id in dev and another in
 * production. Preferences stored as uuids would not survive being restored
 * into another environment, and would silently resolve to nothing rather than
 * failing loudly.
 *
 * Slugs are the taxonomy's portable key — `label` is what gets edited when
 * wording changes, `slug` is what `entity_terms` is reconciled against. It is
 * also what `facet_affinity` wants to hold anyway, so this stores one
 * representation instead of translating between two.
 */

let platformPool: pg.Pool | null = null

function pool(): pg.Pool {
  const url = process.env.PLATFORM_DATABASE_URI ?? process.env.PLATFORM_DATABASE_URL
  if (!url) throw new Error('PLATFORM_DATABASE_URI is not set')
  platformPool ??= new pg.Pool({ connectionString: url, max: 4, statement_timeout: 5_000 })
  return platformPool
}

export type Option = { slug: string; label: string }

export type Vocabulary = {
  /** §17 step 1 — "What are you into?" */
  interests: Option[]
  /** The genre axis: finer than `type`, and what makes this read as a taste profile. */
  topics: Option[]
  /** §17 step 2 — "Where do you spend time?" Scoped to this city. */
  areas: Option[]
  /** §17 step 3 — "You're…" */
  personas: Option[]
  /** §17 step 4 — budget, skippable. */
  budgets: Option[]
}

/**
 * `type` terms that are not things a reader is "into".
 *
 * `editorial` and `unknown` are classification outcomes, not interests —
 * offering "are you into Unknown?" is how a picker built straight off a
 * taxonomy embarrasses itself.
 */
const NON_INTEREST_TYPES = new Set(['editorial', 'unknown'])

/** §17's four, in its order. The `audience` facet carries eleven more that answer a different question. */
const PERSONA_SLUGS = ['expat', 'local', 'tourist', 'business-traveller']

async function termsFor(facetKey: string): Promise<Option[]> {
  const { rows } = await pool().query<{ slug: string; label: string }>(
    `SELECT t.slug, t.label
       FROM engine.terms t
       JOIN engine.facets f ON f.id = t.facet_id
      WHERE f.key = $1
      ORDER BY t.label`,
    [facetKey],
  )
  return rows.map((r) => ({ slug: String(r.slug), label: String(r.label) }))
}

export async function loadVocabulary(): Promise<Vocabulary> {
  const site = await getSiteConfig()
  const [types, topics, personaPool, budgets, tree] = await Promise.all([
    termsFor('type'),
    termsFor('topic'),
    termsFor('audience'),
    termsFor('price_band'),
    locationTree(site.slug),
  ])

  // Areas come from the same tree `/areas` renders, so the chips a reader
  // picks are the ones the site actually files things under.
  const areas: Option[] = tree.local.regions
    .flatMap((region) => region.areas)
    .map((area) => ({ slug: area.slug, label: area.label }))

  const personaBySlug = new Map(personaPool.map((p) => [p.slug, p]))

  return {
    interests: types.filter((t) => !NON_INTEREST_TYPES.has(t.slug)),
    topics,
    areas,
    personas: PERSONA_SLUGS.map((slug) => personaBySlug.get(slug)).filter(
      (p): p is Option => Boolean(p),
    ),
    // $ before $$$$. `ORDER BY label` happens to sort those correctly as
    // strings, but ordering money by string comparison is luck, not intent.
    budgets: [...budgets].sort((a, b) => a.label.length - b.label.length),
  }
}

// --- what a reader has chosen ---------------------------------------------

export type StatedPrefs = {
  interests: string[]
  topics: string[]
  areas: string[]
  persona: string | null
  budget: string | null
  updatedAt?: string
}

export const EMPTY_PREFS: StatedPrefs = {
  interests: [],
  topics: [],
  areas: [],
  persona: null,
  budget: null,
}

/** Keeps only slugs the vocabulary still offers, so a retired term quietly drops out. */
function keep(values: string[], options: Option[]): string[] {
  const known = new Set(options.map((o) => o.slug))
  return values.filter((v) => known.has(v))
}

export async function loadPrefs(identityId: string): Promise<StatedPrefs> {
  const { rows } = await pool().query<{ stated_prefs: unknown }>(
    `SELECT stated_prefs FROM engine.identities WHERE id = $1`,
    [identityId],
  )
  const raw = rows[0]?.stated_prefs
  if (!raw || typeof raw !== 'object') return EMPTY_PREFS
  const value = raw as Partial<StatedPrefs>
  return {
    interests: Array.isArray(value.interests) ? value.interests.map(String) : [],
    topics: Array.isArray(value.topics) ? value.topics.map(String) : [],
    areas: Array.isArray(value.areas) ? value.areas.map(String) : [],
    persona: typeof value.persona === 'string' ? value.persona : null,
    budget: typeof value.budget === 'string' ? value.budget : null,
    updatedAt: typeof value.updatedAt === 'string' ? value.updatedAt : undefined,
  }
}

export function hasChosen(prefs: StatedPrefs): boolean {
  return prefs.interests.length > 0 || prefs.topics.length > 0 || prefs.areas.length > 0
}

// --- writing ---------------------------------------------------------------

/**
 * Weight given to something a reader stated outright.
 *
 * 1.0 — the top of §17's own signal table, level with "saved / shared". Someone
 * answering a direct question about themselves is at least as strong a signal
 * as a save, and it is the only signal that exists before any behaviour does.
 */
const STATED_WEIGHT = 1

/** `{ facet_key: { term_slug: weight } }` — the shape §10's blend reads. */
export function buildFacetAffinity(
  prefs: StatedPrefs,
  vocabulary: Vocabulary,
): Record<string, Record<string, number>> {
  const weigh = (slugs: string[], options: Option[]): Record<string, number> =>
    Object.fromEntries(keep(slugs, options).map((s) => [s, STATED_WEIGHT]))

  const affinity: Record<string, Record<string, number>> = {}
  const pairs: [string, Record<string, number>][] = [
    ['type', weigh(prefs.interests, vocabulary.interests)],
    ['topic', weigh(prefs.topics, vocabulary.topics)],
    ['location', weigh(prefs.areas, vocabulary.areas)],
    ['audience', weigh(prefs.persona ? [prefs.persona] : [], vocabulary.personas)],
    ['price_band', weigh(prefs.budget ? [prefs.budget] : [], vocabulary.budgets)],
  ]
  for (const [facet, weights] of pairs) {
    if (Object.keys(weights).length > 0) affinity[facet] = weights
  }
  return affinity
}

/**
 * Persists the picks in both places they belong, in one transaction.
 *
 * `identities.stated_prefs` holds the **answers** as given;
 * `user_profiles.facet_affinity` holds the **weights** ranking reads. Two
 * views of one thing, written together so they cannot disagree — the failure
 * mode F132 spent a whole wave reconciling on a different pair of stores.
 *
 * `n_meaningful` is deliberately **not** touched. It counts revealed
 * behaviour and is α's input; bumping it here would make stating a preference
 * dilute the very seed it just set.
 */
export async function savePrefs(identityId: string, prefs: StatedPrefs): Promise<void> {
  const site = await getSiteConfig()
  const vocabulary = await loadVocabulary()

  // Sanitised against the live vocabulary before storage, so a hand-posted
  // form cannot write slugs that do not exist.
  const clean: StatedPrefs = {
    interests: keep(prefs.interests, vocabulary.interests),
    topics: keep(prefs.topics, vocabulary.topics),
    areas: keep(prefs.areas, vocabulary.areas),
    persona: keep(prefs.persona ? [prefs.persona] : [], vocabulary.personas)[0] ?? null,
    budget: keep(prefs.budget ? [prefs.budget] : [], vocabulary.budgets)[0] ?? null,
    updatedAt: new Date().toISOString(),
  }
  const affinity = buildFacetAffinity(clean, vocabulary)

  const client = await pool().connect()
  try {
    await client.query('BEGIN')
    await client.query(
      `UPDATE engine.identities SET stated_prefs = $2::jsonb, updated_at = now() WHERE id = $1`,
      [identityId, JSON.stringify(clean)],
    )
    // site_id comes from the slug rather than being passed in, so a caller
    // cannot write one reader's profile against another city.
    await client.query(
      `INSERT INTO engine.user_profiles (user_id, site_id, facet_affinity, updated_at)
            SELECT $1, s.id, $3::jsonb, now() FROM engine.sites s WHERE s.slug = $2
       ON CONFLICT (user_id, site_id)
       DO UPDATE SET facet_affinity = EXCLUDED.facet_affinity, updated_at = now()`,
      [identityId, site.slug, JSON.stringify(affinity)],
    )
    await client.query('COMMIT')
  } catch (error) {
    await client.query('ROLLBACK')
    throw error
  } finally {
    client.release()
  }
}

/**
 * "We think you like: Japanese food, Senopati, rooftop bars" — §17's readback.
 *
 * Shown so it can be corrected. §17: *"Corrections are high-quality training
 * signal."* A reader telling us we were wrong about them is worth more than a
 * click, and they cannot correct what they cannot see.
 */
export function describePrefs(prefs: StatedPrefs, vocabulary: Vocabulary): string[] {
  const label = (slugs: string[], options: Option[]): string[] => {
    const bySlug = new Map(options.map((o) => [o.slug, o.label]))
    return slugs.map((s) => bySlug.get(s)).filter((l): l is string => Boolean(l))
  }
  return [
    ...label(prefs.interests, vocabulary.interests),
    ...label(prefs.topics, vocabulary.topics),
    ...label(prefs.areas, vocabulary.areas),
    ...(prefs.budget ? label([prefs.budget], vocabulary.budgets) : []),
  ]
}
