/**
 * Local, package-scoped version of the CI lint E0.6 owns (PROGRESS.md
 * Wave 1): fails if a `'jakarta'` or `'bali'` string literal appears
 * anywhere under this package's source. E0.6 is responsible for wiring
 * the repo-wide `engine/` version of this check into CI; this script lets
 * this package prove the "zero site-name literals" acceptance criterion
 * on its own, and can be lifted wholesale into that repo-wide check.
 *
 * Deliberately excludes: node_modules, .next, dist, this script itself
 * (it has to mention the banned words to describe what it bans), and
 * runtime config files (.env / .env.example) whose *values* are legitimate
 * per-deployment data, not code literals — SITE_SLUG=jakarta in a
 * deployment's env is the mechanism ARCHITECTURE.md §3.5 prescribes, not
 * a violation of it. What must never appear is the string baked into
 * source: `if (site === 'jakarta')`.
 *
 * One more deliberate exclusion: src/migrations/**. Those files are
 * generated from the live seeded taxonomy (now_platform.engine.terms,
 * ARCHITECTURE.md section 4), and the *location* facet legitimately
 * contains terms named "jakarta" and "bali" as places in the location
 * tree - section 3.5 even documents Jakarta's archive carrying "Bali
 * Updates" articles, i.e. the word "bali" appearing as data inside the
 * Jakarta city DB is expected, not a violation. Banning the word from
 * generated SQL enum definitions would make this package impossible to
 * migrate at all, without stopping a single line of actual
 * `if (site === 'jakarta')` branching logic. Flagged for whoever wires
 * the repo-wide E0.6 lint, so it excludes generated migrations too and
 * only scans real application logic.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const dirname = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(dirname, '..')

// `test/fixtures` holds a REAL E1.2 body_blocks sample pulled from an
// actual archive article ("NIS Jakarta" school) for the round-trip
// verification script — that is editorial content data, not application
// code, and mentioning a city name in a magazine article's prose is not
// what this lint is protecting against.
const EXCLUDED_DIRS = new Set(['node_modules', '.next', 'dist', 'build', '.git', 'migrations', 'fixtures'])
const EXCLUDED_FILES = new Set([path.basename(fileURLToPath(import.meta.url)), '.env', '.env.example'])
const SOURCE_EXT = new Set(['.ts', '.tsx', '.js', '.mjs', '.jsx', '.json'])

const BANNED = [/\bjakarta\b/i, /\bbali\b/i]

const offenders = []

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    if (EXCLUDED_DIRS.has(entry)) continue
    const full = path.join(dir, entry)
    const stat = statSync(full)
    if (stat.isDirectory()) {
      walk(full)
      continue
    }
    if (EXCLUDED_FILES.has(entry)) continue
    if (!SOURCE_EXT.has(path.extname(entry))) continue
    // payload-types.ts / migration snapshot json are generated artifacts,
    // not authored code — a seeded slug value flowing through generated
    // enum types would be data, not a literal decision in our code.
    if (entry === 'payload-types.ts') continue

    const content = readFileSync(full, 'utf-8')
    const lines = content.split('\n')
    lines.forEach((line, i) => {
      for (const pattern of BANNED) {
        if (pattern.test(line)) {
          offenders.push(`${path.relative(root, full)}:${i + 1}: ${line.trim()}`)
        }
      }
    })
  }
}

walk(root)

if (offenders.length > 0) {
  console.error(`[lint-site-literals] FAILED — ${offenders.length} site-name literal(s) found:\n`)
  for (const o of offenders) console.error(`  ${o}`)
  process.exit(1)
}

console.log('[lint-site-literals] OK — zero site-name literals under engine/packages/cms')
process.exit(0)
