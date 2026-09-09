/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/agent/:path*',
        destination: `${process.env.BACKEND_URL || 'http://localhost:8000'}/api/agent/:path*`,
      },
      {
        source: '/health',
        destination: `${process.env.BACKEND_URL || 'http://localhost:8000'}/health`,
      }
    ];
  },
};

export default nextConfig;
