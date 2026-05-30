/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // ✅ reduce build overhead
  swcMinify: true,

  // ✅ avoid unnecessary server load
  experimental: {
    optimizeCss: true,
  },

  // ✅ prevent massive logs
  devIndicators: {
    buildActivity: false,
  },
};

module.exports = nextConfig;
