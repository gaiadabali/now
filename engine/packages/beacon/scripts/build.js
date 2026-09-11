#!/usr/bin/env node
// Minifies src/beacon.js -> dist/beacon.min.js and reports raw + gzip size.
// No runtime dependency is introduced — terser is a devDependency used only
// at build time; the shipped artifact is a single vanilla-JS file.
'use strict';

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const { minify } = require('terser');

const SRC = path.join(__dirname, '..', 'src', 'beacon.js');
const OUT_DIR = path.join(__dirname, '..', 'dist');
const OUT = path.join(OUT_DIR, 'beacon.min.js');

async function main() {
  const src = fs.readFileSync(SRC, 'utf8');

  const result = await minify(src, {
    compress: {
      passes: 2,
      pure_getters: true
    },
    mangle: {
      // Never mangle the public global or the payload field names literal
      // strings — mangle only touches identifiers, not string keys, but we
      // keep reserved just in case a future refactor introduces top-level
      // names that must stay stable for debugging.
      reserved: ['NOWB']
    },
    format: {
      comments: false
    }
  });

  if (result.error) {
    console.error(result.error);
    process.exit(1);
  }

  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(OUT, result.code, 'utf8');

  const rawBytes = Buffer.byteLength(result.code, 'utf8');
  const gz = zlib.gzipSync(Buffer.from(result.code, 'utf8'), { level: 9 });
  const brotli = zlib.brotliCompressSync
    ? zlib.brotliCompressSync(Buffer.from(result.code, 'utf8'))
    : null;

  console.log('Built: ' + path.relative(process.cwd(), OUT));
  console.log('  raw:     ' + rawBytes + ' bytes');
  console.log('  gzip:    ' + gz.length + ' bytes (' + (gz.length / 1024).toFixed(2) + ' KB)');
  if (brotli) {
    console.log('  brotli:  ' + brotli.length + ' bytes (' + (brotli.length / 1024).toFixed(2) + ' KB)');
  }

  const BUDGET_BYTES = 4 * 1024;
  if (gz.length >= BUDGET_BYTES) {
    console.error('FAIL: gzipped size ' + gz.length + ' >= ' + BUDGET_BYTES + ' byte budget');
    process.exit(1);
  } else {
    console.log('OK: within < 4 KB gzipped budget (' + (BUDGET_BYTES - gz.length) + ' bytes to spare)');
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
