import path from 'node:path'

import { withPayload } from '@payloadcms/next/withPayload'

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required by Dockerfile's `COPY --from=builder /app/.next/standalone`.
  // Next only emits that directory when output is set, so without this the
  // image build fails at the COPY step — the Dockerfile was written for a
  // standalone build that the config never asked for.
  output: 'standalone',
  // This app is an npm workspace member, so its dependencies live in
  // engine/node_modules rather than beside it. Without an explicit tracing
  // root Next infers one from the app directory and traces a tree that no
  // longer contains them, producing a standalone bundle that is missing
  // modules at runtime.
  outputFileTracingRoot: path.join(import.meta.dirname, '../..'),
  // Payload's admin bundle pulls in a couple of packages that assume a
  // Node runtime; keep this minimal and let @payloadcms/next own the rest.
  experimental: {
    reactCompiler: false,
  },
}

export default withPayload(nextConfig, { devBundleServerPackages: false })
