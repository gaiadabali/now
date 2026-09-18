#!/usr/bin/env node
/**
 * S1.3 — move each city's `nav` and brand marks out of the baked config file
 * and into `engine.sites`, so a console has something to govern.
 *
 * `getSiteConfig()` now reads the registry with the file underneath it. That
 * change is inert until the registry actually holds something: every row ships
 * with `nav`, `brand_tokens`, `home_rails` and `ranking_weights` at
 * `'{}'::jsonb`, which the loader correctly reads as "ungoverned, use the
 * file". This is the one-time lift that gives the console a starting point
 * identical to what readers see today.
 *
 * **Why this is Node and not `now-db`.** The seed's source is
 * `<slug>/site/site.config.json` and its consumer is the reader app, both of
 * which are typed by `apps/web/src/lib/site.ts`. A Python implementation would
 * have to re-derive that file's shape and could then disagree with the only
 * code that reads it — the failure mode being a nav that validates in the
 * seeder and is rejected by `navFrom()`. The other `engine.sites` data
 * backfill (the format→decay policy) lives in `now_db` because its source is
 * the taxonomy, which is Python's.
 *
 * **It will not overwrite a console edit.** A column that already holds
 * anything other than `{}` is left alone unless `--force` is passed. Re-running
 * this after someone has retitled a section in the console must not quietly
 * put the old nav back — that is the kind of scripted regression nobody thinks
 * to look for.
 *
 * Usage:
 *   node scripts/seed-site-registry.mjs --dry-run
 *   node scripts/seed-site-registry.mjs
 *   node scripts/seed-site-registry.mjs --slug bali --force
 *
 * Reads PLATFORM_DATABASE_URL, or PLATFORM_DATABASE_URI — both are set on the
 * deployed web services, and local environments tend to set one.
 */
import { readFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import pg from 'pg'

const args = process.argv.slice(2)
const dryRun = args.includes('--dry-run')
const force = args.includes('--force')
const onlySlug = args.includes('--slug') ? args[args.indexOf('--slug') + 1] : null

const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = process.env.NOW_REPO_ROOT ?? resolve(here, '..', '..', '..', '..')

const url = process.env.PLATFORM_DATABASE_URL ?? process.env.PLATFORM_DATABASE_URI
if (!url) {
  console.error('[seed] Neither PLATFORM_DATABASE_URL nor PLATFORM_DATABASE_URI is set.')
  process.exit(2)
}

/** `{}` — the default every jsonb column on `sites` ships with. */
const isUngoverned = (value) =>
  value === null ||
  value === undefined ||
  (typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length === 0)

const pool = new pg.Pool({ connectionString: url, max: 2, connectionTimeoutMillis: 5_000 })
let changed = 0
let skipped = 0
let missing = 0

try {
  const { rows: sites } = await pool.query(
    `SELECT slug, nav, brand_tokens FROM engine.sites
      WHERE status <> 'disabled' ${onlySlug ? 'AND slug = $1' : ''}
      ORDER BY slug`,
    onlySlug ? [onlySlug] : [],
  )

  if (sites.length === 0) {
    console.error(`[seed] No matching site in engine.sites${onlySlug ? ` for slug "${onlySlug}"` : ''}.`)
    process.exit(1)
  }

  for (const site of sites) {
    const file = join(repoRoot, site.slug, 'site', 'site.config.json')
    let config
    try {
      config = JSON.parse(await readFile(file, 'utf8'))
    } catch {
      // A registered city with no config file in this checkout is not an
      // error: `test` is a provisioning fixture, and a future city may be
      // registered before its config lands.
      console.log(`[seed] ${site.slug}: no config file at ${file} — skipped`)
      missing += 1
      continue
    }

    const updates = []
    const values = []

    if (Array.isArray(config.nav) && config.nav.length > 0) {
      if (isUngoverned(site.nav) || force) {
        values.push(JSON.stringify(config.nav))
        updates.push(`nav = $${values.length}::jsonb`)
      } else {
        console.log(`[seed] ${site.slug}: nav already governed (${JSON.stringify(site.nav).slice(0, 60)}…) — kept`)
      }
    }

    if (config.brand && typeof config.brand === 'object') {
      if (isUngoverned(site.brand_tokens) || force) {
        values.push(JSON.stringify(config.brand))
        updates.push(`brand_tokens = $${values.length}::jsonb`)
      } else {
        console.log(`[seed] ${site.slug}: brand_tokens already governed — kept`)
      }
    }

    if (updates.length === 0) {
      skipped += 1
      continue
    }

    values.push(site.slug)
    const sql = `UPDATE engine.sites SET ${updates.join(', ')}, updated_at = now() WHERE slug = $${values.length}`

    if (dryRun) {
      console.log(`[seed] ${site.slug}: WOULD SET ${updates.map((u) => u.split(' =')[0]).join(', ')}`)
      console.log(`         nav items: ${Array.isArray(config.nav) ? config.nav.length : 0}`)
    } else {
      await pool.query(sql, values)
      console.log(`[seed] ${site.slug}: set ${updates.map((u) => u.split(' =')[0]).join(', ')}`)
    }
    changed += 1
  }
} finally {
  await pool.end()
}

console.log(
  `\n[seed] ${dryRun ? 'dry run — nothing written' : 'done'}: ${changed} site(s) ${dryRun ? 'would change' : 'changed'}, ` +
    `${skipped} already seeded, ${missing} without a config file.`,
)
