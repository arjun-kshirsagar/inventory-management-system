import type { NextConfig } from "next";

const apiUrl = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Local and Docker development proxy through Next. Vercel's project-level
  // rewrites route /api/* directly to the FastAPI service instead.
  async rewrites() {
    return process.env.VERCEL
      ? []
      : [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
};

export default nextConfig;
