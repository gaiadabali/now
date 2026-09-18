import { DefaultTemplate } from '@payloadcms/next/templates'
import type { ReactNode } from 'react'

/**
 * The one thing every top-level Payload custom view in this app has to do
 * for itself, and the reason it is a shared file rather than three copies.
 *
 * `admin.components.views` (payload.config.ts) does not carry a "give me the
 * sidebar" flag — `AdminViewConfig` is `{ Component, exact?, meta?, path?,
 * sensitive?, strict? }`, nothing about a template. Payload's own catch-all
 * (`@payloadcms/next`'s `RootPage` → `getRouteData`) only ever sets
 * `templateType` for the handful of BUILT-IN one-segment views it names
 * itself (account, login, logout, …); a route that reaches a custom view
 * through the generic fallback — which is every path in this app's
 * `views` map, because none of them is a built-in name — gets `templateType:
 * undefined` and RootPage renders it as bare content with NO wrapper at all.
 *
 * Found by driving this ticket's own acceptance criterion rather than by
 * reading a doc: `curl` against `/team-editor/classification` returned 200
 * with the right heading and the right data, which looked like a pass, right
 * up until a real browser screenshot showed no sidebar and a DOM dump showed
 * no `<aside class="nav">` at all — the fallback path Payload takes for an
 * unrecognised view key never touches `templateType`. The masthead this
 * ticket deletes was replaced by *nothing* until this file existed.
 *
 * `DefaultTemplate` is the exact component Payload's own catch-all renders
 * around a collection screen (`@payloadcms/next/templates`, confirmed against
 * `node_modules/@payloadcms/next/dist/templates/Default/index.js` before
 * relying on it) — the same sidebar, the same header, the same theme
 * provider. Wrapping our own content in it here is not an imitation of
 * Payload's chrome; it is Payload's chrome, called the way Payload's own
 * views call it.
 */

/**
 * The slice of `AdminViewServerProps` (`payload/dist/admin/views/index.d.ts`)
 * this file actually needs. Typed by hand rather than importing the whole
 * union: everything below is spread directly onto our Component as top-level
 * props by `@payloadcms/ui`'s `RenderServerComponent` (it treats a server
 * component's `serverProps` as one flat prop bag, not a nested object), so
 * declaring only what `DefaultTemplate` reads keeps this honest about the
 * actual contract instead of the full, mostly-irrelevant server-view shape.
 */
export type AdminViewFrameProps = {
  children: ReactNode
  /** A class on the wrapper INSIDE the template — e.g. `classify__main`,
   * `console__main` — not on `DefaultTemplate` itself. */
  contentClassName?: string
  i18n: unknown
  initPageResult: {
    locale?: unknown
    permissions: unknown
    req: unknown & { user?: unknown }
    visibleEntities: unknown
  }
  params?: unknown
  payload: unknown
  searchParams?: unknown
}

export function AdminViewFrame({
  children,
  contentClassName,
  i18n,
  initPageResult,
  params,
  payload,
  searchParams,
}: AdminViewFrameProps) {
  return (
    // The cast matches Payload's own Root/index.js call to `DefaultTemplate`:
    // that file also passes `req`, `permissions` and friends straight through
    // from `initPageResult` without re-narrowing them, because `PayloadRequest`
    // and `SanitizedPermissions` are declared in `payload`'s own server-only
    // module graph, which this shared, template-agnostic file deliberately
    // does not import — see `AdminViewFrameProps` above.
    <DefaultTemplate
      {...({
        i18n,
        locale: initPageResult.locale,
        params,
        payload,
        permissions: initPageResult.permissions,
        req: initPageResult.req,
        searchParams,
        user: initPageResult.req?.user,
        visibleEntities: initPageResult.visibleEntities,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any -- see
        // the comment above: this file deliberately does not import
        // `payload`'s server-only types, so the boundary to a typed prop
        // (`DefaultTemplateProps`) has to be crossed with one explicit `any`
        // rather than a chain of hand-copied type declarations that can drift
        // from the real ones.
      } as any)}
    >
      {contentClassName ? <div className={contentClassName}>{children}</div> : children}
    </DefaultTemplate>
  )
}
