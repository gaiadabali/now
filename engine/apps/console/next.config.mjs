import path from 'node:path'

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emits .next/standalone, which the Dockerfile copies. Without it that
  // COPY fails — exactly how the CMS image was broken before this branch.
  output: 'standalone',
  // This app is an npm workspace member, so its dependencies live in
  // engine/node_modules rather than beside it. Without an explicit tracing
  // root Next infers one from the app directory and traces a tree that no
  // longer contains them, producing a standalone bundle that is missing
  // modules at runtime.
  outputFileTracingRoot: path.join(import.meta.dirname, '../..'),
  reactStrictMode: true,
  // `pg` opens TCP sockets and must not be traced into a client bundle.
  // Keeping it external also stops the bundler inlining its optional native
  // deps, which is a known source of build failures in standalone output.
  serverExternalPackages: ['pg'],
}
export default nextConfig
