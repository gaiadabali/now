import Link from 'next/link'
import { notFound } from 'next/navigation'

import { requireStaffAdmin } from '@/lib/auth'
import { getRegistrySite } from '@/lib/queries'
import { loadSiteConfigFile } from '@/lib/site'
import type { SiteConfig } from '@/lib/site'

import { PLATFORM_ROOT } from '../../paths'
import { brandReport, modulesReport, navReport, railsReport } from '../../registry'
import { BrandForm, ModulesForm, NavForm, RailsForm } from './SiteEditor'

/**
 * `/team-editor/platform/sites/[slug]` — edit one site's governed config.
 *
 * Role-gated here, before any query — same reasoning as the index and every
 * commerce page (`lib/auth.ts`): a layout guard would not stop a direct
 * request to this URL from reaching `getRegistrySite`.
 *
 * The file read is the one place this app reads a city's config file for a
 * city that is **not** its own `SITE_SLUG` — `loadSiteConfigFile` exists
 * because of that (see its comment in `lib/site.ts`). It can legitimately
 * fail — `test/site/` in this checkout has no `site.config.json` — and that
 * is not this page's error: it means the field has no fallback to show
 * alongside the registry value, not that the page is broken.
 */
export async function SiteDetailView({ slug }: { slug: string }) {
  await requireStaffAdmin()

  const site = await getRegistrySite(slug)
  if (!site) notFound()

  let file: SiteConfig | null = null
  let fileError: string | null = null
  try {
    file = await loadSiteConfigFile(slug)
  } catch {
    fileError = 'No config file was found for this site in this checkout.'
  }

  const nav = navReport(site.nav)
  const brand = brandReport(site.brand_tokens)
  const rails = railsReport(site.home_rails)
  const modules = modulesReport(site.enabled_modules)

  return (
    <>
      <Link className="platform__breadcrumb" href={PLATFORM_ROOT}>
        ← Sites
      </Link>
      <h1>{site.name}</h1>
      <p className="platform__sub">
        <code>{site.slug}</code> · {site.hostname} · {site.status}
      </p>

      <h2>Nav</h2>
      <Compare
        governed={nav.governed}
        registry={nav.raw}
        registryLabel={nav.governed ? 'In the console' : nav.emptyColumn ? 'Ungoverned ({})' : 'Invalid — rejected on read'}
        file={file?.nav ?? null}
        fileError={fileError}
        hasFileField
      />
      {!nav.governed && fileError ? (
        <p className="platform__notice platform__notice--bad">
          This site is ungoverned <em>and</em> has no config file in this checkout —
          <code> getSiteConfig()</code> will throw on this field rather than degrade, because the
          file read that would supply the fallback happens before the try/catch that protects the
          registry read (see <code>lib/site.ts</code>). Govern the nav here, or restore the file.
        </p>
      ) : null}
      <NavForm slug={site.slug} siteName={site.name} initial={nav.effective ?? file?.nav ?? []} />

      <h2>Brand marks</h2>
      <p className="platform__sub">
        {brand.governed
          ? 'At least one mark is governed here; any left blank still comes from the file.'
          : 'Nothing is governed — every mark comes from the config file.'}
      </p>
      <Compare
        governed={brand.governed}
        registry={site.brand_tokens}
        registryLabel={brand.governed ? 'In the console (governed fields only)' : 'Ungoverned ({})'}
        file={file?.brand ?? null}
        fileError={fileError}
        hasFileField
      />
      {!brand.governed && fileError ? (
        <p className="platform__notice platform__notice--bad">
          This site is ungoverned <em>and</em> has no config file in this checkout — brand marks
          have no source to fall back to, and the reader will render whatever
          <code>SiteConfig</code>&rsquo;s own defaults produce for a missing file (see the nav
          notice above; the same code path applies here).
        </p>
      ) : null}
      <BrandForm slug={site.slug} siteName={site.name} initial={brand.fields} placeholders={file?.brand ?? null} />

      <h2>Home rail order</h2>
      <Compare
        governed={rails.governed}
        registry={rails.raw}
        registryLabel={rails.governed ? 'In the console' : rails.emptyColumn ? 'Ungoverned ({})' : 'Invalid — rejected on read'}
        file={null}
        fileError="Registry-only — there is no equivalent field in the config file. An ungoverned or empty order means the homepage uses its own built-in default, which is what it does today."
        hasFileField={false}
      />
      <RailsForm slug={site.slug} siteName={site.name} initial={rails.effective ?? []} />

      <h2>Modules (P0.3)</h2>
      <p className="platform__sub">
        Registry-only, like the rail order — there is no config-file equivalent. Every module a
        reader route or dashboard panel gates on (<code>lib/modules.ts</code>&rsquo;s{' '}
        <code>moduleEnabled()</code>) is listed here; nothing is enabled that is not one of these.
      </p>
      <ModulesForm slug={site.slug} siteName={site.name} all={modules.all} initial={modules.enabled} />
    </>
  )
}

/**
 * The side-by-side `getSiteConfig()` merges without showing its work
 * (S5.1's third requirement). Whichever column is what a reader actually
 * sees is marked "winning" — computed the same way the merge is: the
 * registry wins when `governed` is true, the file otherwise.
 */
function Compare({
  governed,
  registry,
  registryLabel,
  file,
  fileError,
  hasFileField,
}: {
  governed: boolean
  registry: unknown
  registryLabel: string
  file: unknown
  fileError: string | null
  /**
   * False for `home_rails`: it has no column in the config file at all, so
   * the right-hand side is never "winning" — there is nothing there to win.
   * True for `nav`/`brand_tokens`, where `fileError` (when set) means the
   * fallback that *should* exist could not be read, which is worth marking
   * differently from "this field simply has no file equivalent".
   */
  hasFileField: boolean
}) {
  // The registry wins exactly when `getSiteConfig()`'s merge would use it —
  // `governed` is computed by the same predicate, so this label is never a
  // second guess at what the reader does.
  const fileWins = hasFileField && !governed && !fileError
  return (
    <div className="platform__compare">
      <div className={`platform__compare-col ${governed ? 'platform__compare-col--winning' : ''}`}>
        <p className="platform__compare-head">{registryLabel}</p>
        <pre>{JSON.stringify(registry, null, 2)}</pre>
      </div>
      <div className={`platform__compare-col ${fileWins ? 'platform__compare-col--winning' : ''}`}>
        <p className="platform__compare-head">In the config file{fileWins ? ' (winning)' : ''}</p>
        {fileError ? <p className="platform__muted">{fileError}</p> : <pre>{JSON.stringify(file, null, 2)}</pre>}
      </div>
    </div>
  )
}
