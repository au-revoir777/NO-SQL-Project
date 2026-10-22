import { headers } from "next/headers";
import type { ReactNode } from "react";

import { requireAdmin } from "@/lib/server/session";

/**
 * Admin pages (Rules, Users, Audit). The role is checked on the server for every
 * request; analysts get the 403 page with HTTP status 403. The API enforces the
 * same rule independently on every /api/v1/admin and /api/v1/rules route.
 */
export default async function AdminLayout({ children }: { children: ReactNode }) {
  await requireAdmin((await headers()).get("x-pathname") ?? "/");
  return children;
}
