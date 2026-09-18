import path from 'node:path'

import { withPayload } from '@payloadcms/next/withPayload'

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emits .next/standalone — a self-contained server bundle with only the
  // node_modules it actually imports. Keeps the runtime image small and is
  // what the Dockerfile copies.
  output: 'standalone',
  // Lets two people (or two agents) work this app at once.
  //
  // `next dev` and `next build` both write to the same `distDir`, so two of
  // them in one checkout corrupt each other's output — which is a real
  // constraint here, because PROGRESS.md's execution model is parallel agents
  // sharing a tree under a file-ownership map. Ownership stops them editing
  // the same source; it does nothing about them writing the same build
  // directory.
  //
  // Unset everywhere that matters: CI, the Dockerfile and every normal local
  // run get `.next`, which is the only value `output: 'standalone'` and the
  // image's COPY paths know about. `.next-*` is gitignored alongside it.
  distDir: process.env.NEXT_DIST_DIR ?? '.next',
  // This app is an npm workspace member, so its dependencies live in
  // engine/node_modules rather than beside it. Without an explicit tracing
  // root Next infers one from the app directory and traces a tree that no
  // longer contains them, producing a standalone bundle that is missing
  // modules at runtime.
  outputFileTracingRoot: path.join(import.meta.dirname, '../..'),
  reactStrictMode: true,
  images: {
    // Comp phase: images are still served by the legacy WordPress hosts.
    // These entries disappear once E1.3 mirrors media into Garage and
    // imgproxy fronts it — see ARCHITECTURE.md §14.
    remotePatterns: [
      { protocol: 'https', hostname: '**.nowbali.co.id' },
      { protocol: 'https', hostname: '**.nowjakarta.co.id' },
    ],
    formats: ['image/avif', 'image/webp'],
  },
}
// Wrapped because this app now SERVES the Payload admin at /team-editor
// (docs/ADMIN-CONSOLIDATION.md Phase 2), not merely imports the config for
// the Local API. `withPayload` externalises Payload's server-only dependency
// graph; without it the build tries to bundle things like
// json-schema-to-typescript and fails on `Can't resolve 'cli-color'`.
export default withPayload(nextConfig, { devBundleServerPackages: false })
