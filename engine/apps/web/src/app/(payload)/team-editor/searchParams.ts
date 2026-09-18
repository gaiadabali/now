/**
 * Reading a query string handed to us by Payload rather than by Next.
 *
 * S3.1 turned `classification/**`, `commerce/**` and `staff` from literal Next
 * routes into Payload custom views (`admin.components.views` in
 * payload.config.ts), so they now render inside Payload's own catch-all
 * (`team-editor/[[...segments]]/page.tsx`) instead of owning their own route
 * files. That changes what a page receives: a Next.js page gets
 * `searchParams: Promise<{ [key]: string | string[] | undefined }>`; a Payload
 * view gets the already-resolved object directly (`ServerProps.searchParams`,
 * parsed by `qs` in `@payloadcms/next`'s `RootPage`) — no promise to await,
 * but the same "a repeated key is an array" shape underneath.
 *
 * Every reader in this tree wants one string, so this is the one place that
 * decides what happens to a repeated key: the last one wins, matching how a
 * browser submits a form with a duplicated field name.
 */
export function searchParam(
  searchParams: Record<string, string | string[] | undefined> | undefined,
  key: string,
): string | undefined {
  const value = searchParams?.[key]
  return Array.isArray(value) ? value[value.length - 1] : value
}
