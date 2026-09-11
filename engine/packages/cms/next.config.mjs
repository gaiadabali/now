import { withPayload } from '@payloadcms/next/withPayload'

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Payload's admin bundle pulls in a couple of packages that assume a
  // Node runtime; keep this minimal and let @payloadcms/next own the rest.
  experimental: {
    reactCompiler: false,
  },
}

export default withPayload(nextConfig, { devBundleServerPackages: false })
