import { withPayload } from '@payloadcms/next/withPayload'

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required by Dockerfile's `COPY --from=builder /app/.next/standalone`.
  // Next only emits that directory when output is set, so without this the
  // image build fails at the COPY step — the Dockerfile was written for a
  // standalone build that the config never asked for.
  output: 'standalone',
  // Payload's admin bundle pulls in a couple of packages that assume a
  // Node runtime; keep this minimal and let @payloadcms/next own the rest.
  experimental: {
    reactCompiler: false,
  },
}

export default withPayload(nextConfig, { devBundleServerPackages: false })
