import type { NextConfig } from "next";

// Server-side only (not exposed to the browser) -- the browser always calls
// same-origin /api/*, and Next.js forwards it here. Keeps things same-origin
// in both dev and the docker-compose deployment, with no CORS configuration
// needed on the backend.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
