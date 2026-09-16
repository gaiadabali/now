#!/usr/bin/env node
/**
 * Copies the built beacon into `public/` so the site can serve it (E8.5).
 *
 * The beacon is a standalone vanilla-JS file in `@now-engine/beacon`, not a
 * module the bundler can reach: it reads its own `<script>` tag's `data-*`
 * attributes and derives its endpoint from `document.currentScript.src`.
 * Bundling it would destroy both.
 *
 * So it has to be a static asset — and a static asset checked into `public/`
 * is a copy that goes stale the first time the beacon is fixed and nobody
 * remembers this directory exists. Running the copy at build time means the
 * artifact CI tested always carries the beacon CI tested.
 *
 * Fails loudly rather than skipping. A silent no-op here is a site that stops
 * collecting behaviour with no error anywhere — and behavioural data cannot
 * be backfilled, which is the whole reason ARCHITECTURE §19 ships the beacon
 * before anything consumes it.
 */
import { copyFileSync, mkdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const source = join(here, '..', '..', '..', 'packages', 'beacon', 'dist', 'beacon.min.js')
const destination = join(here, '..', 'public', 'beacon.min.js')

let stats
try {
  stats = statSync(source)
} catch {
  console.error(
    `[sync-beacon] not found: ${source}\n` +
      '  The beacon must be built before the web app. Run `npm run build -w @now-engine/beacon`.',
  )
  process.exit(1)
}

// A zero-byte or truncated file would serve a 200 and collect nothing.
if (stats.size < 1000) {
  console.error(`[sync-beacon] refusing to copy a ${stats.size}-byte beacon — it is not a build.`)
  process.exit(1)
}
if (!readFileSync(source, 'utf8').includes('NOWB')) {
  console.error('[sync-beacon] the source does not define NOWB — wrong file?')
  process.exit(1)
}

mkdirSync(dirname(destination), { recursive: true })
copyFileSync(source, destination)
console.log(`[sync-beacon] ${stats.size} bytes -> public/beacon.min.js`)
