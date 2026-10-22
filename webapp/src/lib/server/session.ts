/**
 * Server-side session lookup for layouts and pages: asks FastAPI's
 * GET /api/v1/auth/me with the incoming request's cookies. The role check on
 * the page is the server's answer, not something the client claims.
 */
import { cookies } from "next/headers";
import { forbidden, redirect } from "next/navigation";

import type { components } from "@/lib/api/schema";

import { apiBaseUrl } from "./api-base";

export type SessionUser = components["schemas"]["UserOut"];

export async function getSessionUser(): Promise<SessionUser | null> {
  const jar = await cookies();
  const cookie = jar
    .getAll()
    .map((c) => `${c.name}=${c.value}`)
    .join("; ");
  if (!cookie.includes("fraudsim_access=")) return null;
  try {
    const res = await fetch(new URL("/api/v1/auth/me", apiBaseUrl()), {
      headers: { cookie, accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const body = (await res.json()) as { user: SessionUser };
    return body.user;
  } catch {
    return null;
  }
}

/** For pages behind the login: the signed-in user, or a redirect to /login. */
export async function requireUser(next = "/"): Promise<SessionUser> {
  const user = await getSessionUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(next)}`);
  return user;
}

/** For admin pages: renders the 403 page (HTTP 403) for anyone else. */
export async function requireAdmin(next = "/"): Promise<SessionUser> {
  const user = await requireUser(next);
  if (user.role !== "admin") forbidden();
  return user;
}
