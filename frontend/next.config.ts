import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  /* config options here */
  eslint: {
    // Disable ESLint during builds - inline styles are required for ImageResponse (OG images)
    ignoreDuringBuilds: false,
  },
};

export default nextConfig;
