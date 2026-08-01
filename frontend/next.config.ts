import type { NextConfig } from "next";
import { BACKEND_URL } from "./lib/constants/backend-url";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // Avatar uploads go through a Server Action; the default 1 MB cap would
  // reject anything between 1–5 MB (the backend's limit) with a hard crash.
  // Match the backend's avatar_max_bytes (5 MB).
  experimental: {
    serverActions: {
      bodySizeLimit: "5mb",
    },
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/api/:path*`,
      },
      {
        source: "/uploads/:path*",
        destination: `${BACKEND_URL}/uploads/:path*`,
      },
    ];
  },
};

export default nextConfig;
