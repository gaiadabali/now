/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emits .next/standalone, which the Dockerfile copies. Without it that
  // COPY fails — exactly how the CMS image was broken before this branch.
  output: 'standalone',
  reactStrictMode: true,
  // `pg` opens TCP sockets and must not be traced into a client bundle.
  // Keeping it external also stops the bundler inlining its optional native
  // deps, which is a known source of build failures in standalone output.
  serverExternalPackages: ['pg'],
}
export default nextConfig
