/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emits .next/standalone — a self-contained server bundle with only the
  // node_modules it actually imports. Keeps the runtime image small and is
  // what the Dockerfile copies.
  output: 'standalone',
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
export default nextConfig
