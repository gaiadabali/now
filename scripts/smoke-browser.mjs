#!/usr/bin/env node
/**
 * The checks curl cannot make: does the admin actually render for a person.
 *
 *   node scripts/smoke-browser.mjs https://now-jakarta.example
 *
 * OPT-IN, and deliberately not part of `scripts/smoke.sh`. It needs Playwright
 * and a downloaded browser, which is a real dependency to put in the default
 * path of a deploy check that otherwise needs only curl. Run it when the admin
 * is what changed.
 *
 * ## Why it exists
 *
 * On 2026-09-17 every `/team-editor` route served 200 with ~55 KB of valid
 * HTML and a blank page, for twenty minutes, behind a passing health check.
 * Supplying `GARAGE_*` at run time switched on a plugin whose client component
 * is resolved through `importMap.js` — generated at build time, without those
 * credentials. An unresolved component renders as nothing rather than as an
 * error.
 *
 * `smoke.sh` now catches that specific class from the bytes alone, by asserting
 * that `getFromImportMap` is absent. That is worth having and it is not the
 * same thing as this. The admin form is CLIENT-rendered: `<form>` and `<input>`
 * are zero in the server HTML whether the page works or not. No amount of
 * grepping proves a person can sign in; only running the page does.
 *
 * The honest division:
 *   smoke.sh            no unresolved components, and a status line
 *   smoke-browser.mjs   the form is really there, and nothing threw
 */

const base = (process.argv[2] ?? '').replace(/\/+$/, '')
if (!base) {
  console.error('usage: node scripts/smoke-browser.mjs <base-url>')
  process.exit(2)
}

let chromium
try {
  ;({ chromium } = await import('playwright'))
} catch {
  console.error(
    'playwright is not installed.\n' +
      '  npm i -D playwright && npx playwright install chromium\n' +
      'This script is opt-in precisely so that smoke.sh does not need it.',
  )
  process.exit(2)
}

let pass = 0
let fail = 0
const ok = (m) => {
  console.log(`  \x1b[32mok\x1b[0m   ${m}`)
  pass += 1
}
const bad = (m) => {
  console.log(`  \x1b[31mFAIL\x1b[0m ${m}`)
  fail += 1
}

const browser = await chromium.launch()
try {
  const page = await browser.newPage()
  const consoleErrors = []
  page.on('console', (m) => m.type() === 'error' && consoleErrors.push(m.text()))
  page.on('pageerror', (e) => consoleErrors.push(String(e)))

  const url = `${base}/team-editor/login`
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45_000 })

  // WAIT ON THE SELECTOR, NOT ON A CLOCK.
  //
  // The first version used `waitUntil: 'networkidle'` and then counted
  // immediately. That is better than a fixed sleep and still the wrong shape:
  // network quiet is a PROXY for "the form exists", and a proxy is exactly
  // what this script was written to stop trusting. now-fc hit the real version
  // of this within an hour of the incident — a 6s wait against a 9.7s first
  // compile reported "still blank, 0 inputs" on a server that was fine, and
  // briefly invented a second root cause.
  //
  // So: wait for the thing being asserted. A slow page then passes once it
  // arrives, and a genuinely blank one fails on the timeout with the right
  // message instead of a misleading count of zero.
  let formArrived = true
  try {
    await page.waitForSelector('input[type="password"]', { state: 'attached', timeout: 30_000 })
  } catch {
    formArrived = false
  }
  if (!formArrived) {
    bad('login never rendered a password field within 30s — blank, or far too slow to use')
  }

  // The three things that make this a sign-in screen rather than a blank one.
  const password = await page.locator('input[type="password"]').count()
  const email = await page.locator('input[type="email"], input[name="email"]').count()
  const submit = await page.locator('button[type="submit"]').count()

  password === 1 ? ok('login has a password field') : bad(`login has ${password} password fields`)
  email === 1 ? ok('login has an email field') : bad(`login has ${email} email fields`)
  submit >= 1 ? ok('login has a submit button') : bad('login has no submit button')

  // A blank page is not empty of markup, it is empty of TEXT. This is the
  // check that would have failed loudest during the incident.
  const text = ((await page.innerText('body')) ?? '').trim()
  text.length > 20
    ? ok(`login renders ${text.length} characters of text`)
    : bad(`login renders only ${text.length} characters — it is blank to a reader`)

  consoleErrors.length === 0
    ? ok('no console errors on the login page')
    : bad(`console errors: ${consoleErrors.slice(0, 3).join(' | ')}`)
} catch (error) {
  bad(`browser check threw: ${error instanceof Error ? error.message : String(error)}`)
} finally {
  await browser.close()
}

console.log(`\n  ${pass} passed, ${fail} failed`)
process.exit(fail > 0 ? 1 : 0)
