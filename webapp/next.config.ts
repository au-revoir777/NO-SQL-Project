import path from "node:path";
import { fileURLToPath } from "node:url";

import type { NextConfig } from "next";

const REPO_ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // The repository root, so Next does not pick up lockfiles above it.
  outputFileTracingRoot: REPO_ROOT,
  turbopack: { root: REPO_ROOT },
  // forbidden() renders app/forbidden.tsx with a real HTTP 403 status.
  experimental: { authInterrupts: true },
  // /api/v1/* is served by the cookie-forwarding route handler in
  // src/app/api/v1/[...path]/route.ts (backend-for-frontend), not a rewrite.
};

export default config;
