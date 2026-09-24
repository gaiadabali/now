import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { excludedTypesFor, type TypeRelations } from './competitorPolicy.ts'

/**
 * The hidden-rival guard's lexicon (Edition 2, WS1 deliverable #2) —
 * TypeScript port of `now_filters.hidden_rival` (`engine/packages/filters/
 * src/now_filters/hidden_rival.py`), which has the full reasoning: a
 * candidate article whose DECLARED type survives the ordinary competitor
 * check may still be centrally about a competing venue that the classifier
 * filed under a different type (the Westin/Kimpton case, docs/
 * EDITION-2-PLAN.md §2). The signal is a `role='featured'` `place_mentions`
 * row whose place NAME matches the taxonomy's own subtype label/alias
 * vocabulary (`type.json`) — never a hardcoded brand list.
 *
 * `hidden_rival_lexicon_overrides.json` is the shared, measured curation
 * (dropping the bare word "club" from `drink` — see that file) both this
 * module and the Python one load, so the two languages' guards cannot
 * silently diverge on which keywords are too ambiguous to use.
 */

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const TAXONOMY_SEED_DIR = path.resolve(__dirname, '../../../../packages/taxonomy/seed')

type TypeJsonChild = { label?: string; aliases?: string[] }
type TypeJsonL1 = { slug: string; children?: TypeJsonChild[] }
type TypeJson = { terms: TypeJsonL1[] }
type Overrides = { excluded_by_type?: Record<string, { words?: string[] }> }

let cachedLexicon: Record<string, string[]> | null = null

function loadOverrides(): Record<string, Set<string>> {
  try {
    const raw = readFileSync(path.join(TAXONOMY_SEED_DIR, 'hidden_rival_lexicon_overrides.json'), 'utf-8')
    const doc = JSON.parse(raw) as Overrides
    const out: Record<string, Set<string>> = {}
    for (const [type, entry] of Object.entries(doc.excluded_by_type ?? {})) {
      out[type] = new Set((entry.words ?? []).map((w) => w.trim().toLowerCase()))
    }
    return out
  } catch {
    // Missing/unreadable overrides file: "no overrides", not an error — see
    // the Python module's identical stance.
    return {}
  }
}

/** L1 `type` slug -> lowercased subtype labels/aliases, minus the measured
 * overrides. Cached — `type.json` is a static file, not per-request data. */
export function loadSubtypeLexicon(): Record<string, string[]> {
  if (cachedLexicon) return cachedLexicon
  const doc = JSON.parse(readFileSync(path.join(TAXONOMY_SEED_DIR, 'terms', 'type.json'), 'utf-8')) as TypeJson
  const overrides = loadOverrides()
  const lexicon: Record<string, string[]> = {}
  for (const l1 of doc.terms) {
    const keywords = new Set<string>()
    for (const child of l1.children ?? []) {
      if (child.label) keywords.add(child.label.trim().toLowerCase())
      for (const alias of child.aliases ?? []) keywords.add(String(alias).trim().toLowerCase())
    }
    const drop = overrides[l1.slug]
    if (drop) for (const w of drop) keywords.delete(w)
    lexicon[l1.slug] = Array.from(keywords).sort()
  }
  cachedLexicon = lexicon
  return lexicon
}

function escapeForRegex(word: string): string {
  return word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** A Postgres POSIX ARE (`~*`) alternation matching any subtype keyword
 * under any of `types`, word-bounded with `\y` — see the Python module's
 * `build_name_pattern` for why `\y` rather than a plain substring match.
 * `null` when `types` contributes no keywords (e.g. only `'unknown'`). */
export function buildNamePattern(types: Iterable<string>): string | null {
  const lexicon = loadSubtypeLexicon()
  const keywords = new Set<string>()
  for (const t of types) for (const k of lexicon[t] ?? []) keywords.add(k)
  if (keywords.size === 0) return null
  const alternation = Array.from(keywords).sort().map(escapeForRegex).join('|')
  return `\\y(${alternation})\\y`
}

/** The pattern for THIS subject: every keyword belonging to any type
 * `excludedTypesFor` already names (competes_with included), minus
 * `'unknown'` (no subtypes of its own). */
export function hiddenRivalPatternForSubject(subjectType: string | null, relations: TypeRelations): string | null {
  const excluded = excludedTypesFor(relations, subjectType)
  excluded.delete('unknown')
  if (excluded.size === 0) return null
  return buildNamePattern(excluded)
}
