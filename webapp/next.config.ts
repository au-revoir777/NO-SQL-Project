import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

// FastAPI base URL, used server-side only. In P2 the /api/v1 proxy becomes a
// cookie-forwarding BFF route handler; in P1 a rewrite is enough.
const API_BASE_URL = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";
const REPO_ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The repository root, so Next does not pick up lockfiles above it.
  outputFileTracingRoot: REPO_ROOT,
  turbopack: { root: REPO_ROOT },
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${API_BASE_URL}/api/v1/:path*` }];
  },
};

export default config;
