#!/usr/bin/env node
/**
 * Fails if any city name, slug or hostname is hardcoded under src/.
 *
 * ARCHITECTURE.md §3.5: ONE app serves every city, differentiated only by
 * env + the site registry. The moment a literal lands in src/, adding a
 * third city stops being a config change. Same guard the CMS package runs.
 *
 * Site identity must arrive via `getSiteConfig()`. Files under
 * `<slug>/site/` and `public/brand/` are per-site data and are exempt.
 */
import { readdir, readFile } from 'node:fs/promises'
import path from 'node:path'

const SRC = path.resolve(import.meta.dirname, '..', 'src')

// Known city tokens. Extend when a city is added — deliberately manual, so
// that provisioning a city forces a look at this list.
const FORBIDDEN = [
  /\bnow\s*!?\s*bali\b/i,
  /\bnow\s*!?\s*jakarta\b/i,
  /\bnowbali\b/i,
  /\bnowjakarta\b/i,
  /\bdenpasar\b/i,
  /\bjabodetabek\b/i,
]

// Comments may name a city when citing a document; code may not. We check
// raw lines and skip ones that are wholly a comment.
const isComment = (line) => /^\s*(\/\/|\*|\/\*)/.test(line)

async function* walk(dir) {
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name)
    if (e.isDirectory()) {
      if (e.name === 'fixtures') continue // comp-phase sample content
      yield* walk(p)
    } else if (/\.(ts|tsx|css)$/.test(e.name)) {
      yield p
    }
  }
}

let failures = 0
for await (const file of walk(SRC)) {
  const lines = (await readFile(file, 'utf8')).split('\n')
  lines.forEach((line, i) => {
    if (isComment(line)) return
    for (const re of FORBIDDEN) {
      if (re.test(line)) {
        console.error(`${path.relative(process.cwd(), file)}:${i + 1}  ${line.trim()}`)
        failures++
      }
    }
  })
}

if (failures) {
  console.error(`\n✗ ${failures} site literal(s) in src/. Read identity from getSiteConfig().`)
  process.exit(1)
}
console.log('✓ no site literals under src/')
